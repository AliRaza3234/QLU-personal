import re
import os
import ast
import math
import json
import asyncio
import aiohttp
import aiomysql
import traceback
import urllib.parse
from collections import defaultdict

from qutils.llm.asynchronous import invoke
from app.core.database import postgres_fetch, postgres_insert
from app.utils.search.aisearch.company.generation.utilities import (
    post_process_gpt_output,
)
from app.utils.search.aisearch.company.generation.elastic import (
    get_source_for_cache,
    profile_query_executor,
    quad_query_executor,
    dual_query_executor,
)
from app.utils.search.aisearch.company.generation.utilities import (
    has_special_characters,
    has_accents,
    remove_accents,
    insert_company_mapping,
)
from app.utils.search.aisearch.company.generation.prompts import (
    WHITE_GUARD_USER_PROMPT,
    WHITE_GUARD_SYSTEM_PROMPT,
    VEILED_DEATH_USER_PROMPT,
    VEILDED_DEATH_SYSTEM_PROMPT,
    COMPANY_MAPPING_SYSTEM_PROMPT,
)


def transform_for_white_death(es_data):
    """
    Transforms Elasticsearch company data into a standardized format for LLM processing.

    This function takes raw company data from Elasticsearch and formats it into a
    consistent structure that can be used by the LLM models for company identification.

    Args:
        es_data (list): List of dictionaries containing company data from Elasticsearch

    Returns:
        list: List of formatted company dictionaries with standardized fields
    """
    formatted_entries = []
    for entry in es_data:
        # Extract basic company information
        company_name = entry.get("li_name", "Unknown Company")
        company_url = f"https://www.linkedin.com/company/{entry.get('li_universalname', 'unknown')}"
        description = entry.get("li_description", "No description available.")

        # Process industries and specialties
        industries = entry.get("li_industries", [])
        specialties = entry.get("li_specialties", [])

        # Ensure industries and specialties are lists
        if not isinstance(industries, list):
            industries = [industries]
        if not isinstance(specialties, list):
            specialties = [specialties]

        # Combine and deduplicate industries and specialties
        industries_and_specialties = set(industries + specialties)
        industries_and_specialties.discard("")
        industries = list(industries_and_specialties) or ["No industries specified."]

        # Get company size
        company_size = entry.get("li_size", "Unknown")

        # Process location information
        locations = []
        confirmed_locations = entry.get("li_confirmedlocations", []) or []

        # Format location strings
        for loc in confirmed_locations:
            if loc:
                country = loc.get("country")
                city = loc.get("city")
                if country and city:
                    locations.append(f"{city}, {country}")
                elif country:
                    locations.append(country)
                elif city:
                    locations.append(city)

        # Deduplicate locations
        location_string = list(set(locations)) or ["No locations specified."]

        # Create standardized company dictionary
        company_dict = {
            "Company Name": company_name,
            "Company URL": company_url,
            "Description": description,
            "Industries": industries,
            "Company Size": company_size,
            "Location": location_string,
        }
        formatted_entries.append(company_dict)

    return formatted_entries


async def white_guard(prompt, company_name, industries, es_results):
    """
    Uses LLM to identify the correct company from search results.

    This function sends company data to an LLM model to determine which company
    from the search results best matches the user's query.

    Args:
        prompt (str): The user's original query
        company_name (str): The name of the company to search for
        industries (list): List of industries the company operates in
        es_results (list): Formatted company data from Elasticsearch

    Returns:
        str: The name of the identified company or None if no match is found
    """
    # Prepare system and user messages for the LLM
    system_message = {
        "role": "system",
        "content": WHITE_GUARD_SYSTEM_PROMPT,
    }
    user_message = {
        "role": "user",
        "content": f"""
            {WHITE_GUARD_USER_PROMPT}

            <Input>
                User Query: {prompt}
                Company Name: {company_name}
                Industries: {industries}
                Company Data: {es_results}
            </Input>
            """,
    }

    # Call the LLM with the prepared messages
    response = await invoke(
        messages=[system_message, user_message],
        temperature=0,
        model="groq/llama-3.3-70b-versatile",
        fallbacks=["openai/gpt-4.1"],
    )

    # Process and return the LLM response
    response = post_process_gpt_output(response)
    return response


async def veiled_death(prompt, company_name, industries, es_results):
    """
    Uses LLM as a fallback method to identify the correct company from search results.

    This function is similar to white_guard but uses a different prompt and model
    approach for cases where the initial search method fails.

    Args:
        prompt (str): The user's original query
        company_name (str): The name of the company to search for
        industries (list): List of industries the company operates in
        es_results (list): Formatted company data from Elasticsearch

    Returns:
        str: The name of the identified company or None if no match is found
    """
    # Prepare system and user messages for the LLM
    system_message = {
        "role": "system",
        "content": VEILDED_DEATH_SYSTEM_PROMPT,
    }
    user_message = {
        "role": "user",
        "content": f"""
            {VEILED_DEATH_USER_PROMPT}

            <Input>
                User Query: {prompt}
                Company Name: {company_name}
                Industries: {industries}
                Company Data: {es_results}
            </Input>
            """,
    }

    # Call the LLM with the prepared messages

    response = await invoke(
        messages=[system_message, user_message],
        temperature=0,
        model="openai/gpt-4o-mini",
        fallbacks=["anthropic/claude-3-5-haiku-latest"],
    )

    # Process and return the LLM response
    response = post_process_gpt_output(response)
    return response


async def white_death(
    prompt, company_name, industries, client, company_mapping_cache=None
):
    """
    Main function for company identification using multiple search strategies.

    This function implements a multi-step approach to identify the correct company:
    1. Check the company mapping cache
    2. Search using profile-based queries
    3. If unsuccessful, try alternative search methods based on company name characteristics

    Args:
        prompt (str): The user's original query
        company_name (str): The name of the company to search for
        industries (str): String representation of a list of industries
        client: The Elasticsearch client
        company_mapping_cache (dict, optional): Cache of previously identified companies

    Returns:
        tuple: A tuple containing (es_id, source) or (None, None) if not found
    """
    # Parse industries from string to list
    industries = ast.literal_eval(industries)

    # Prepare query parameters
    query_industries = tuple(industries) if industries else ()
    target_count = 6
    location = "United States"

    # Sanitize company name for SQL query
    safe_company_name = company_name.replace("'", "''")

    # Check if company is in the cache
    cache_hit_query = f"""
            SELECT name, location, total_counts, universal_name
                FROM (
                    SELECT name, industry, location, universal_name,
                        SUM(counts) OVER (PARTITION BY name, location) AS total_counts
                    FROM company_mapping_universalname
                    WHERE name = '{safe_company_name}'
                    AND location = '{location}'
                    {f'AND industry IN {query_industries}' if query_industries else ''}
                ) AS subquery
                WHERE total_counts >= {target_count}
                GROUP BY name, location, total_counts, universal_name
                {f'HAVING COUNT(DISTINCT industry) = {len(query_industries)}' if query_industries else ''};
        """
    try:
        # Try to get company from cache
        if company_mapping_cache:
            cache = company_mapping_cache.get((company_name, location), None)
        else:
            cache = await postgres_fetch(cache_hit_query)
        if cache:
            es_id, source = await get_source_for_cache(cache[3], client)
            return es_id, source
    except:
        pass

    # If not in cache, search using profile-based query
    es_results = await profile_query_executor(company_name)
    data_to_transform = [item[1] for item in es_results]
    transformed_data = transform_for_white_death(data_to_transform)
    li_name = await white_guard(prompt, company_name, industries, transformed_data)

    source = None
    es_id = None

    # Process results from profile-based search
    if li_name:
        # Find the matching company in the results
        for result in data_to_transform:
            if result.get("li_name", "").lower().strip() == li_name.lower().strip():
                source = result
                break
        es_id = next(
            (
                item[0]
                for item in es_results
                if item[1].get("li_name").lower().strip() == li_name.lower().strip()
            ),
            None,
        )
        try:
            # Cache the successful match
            identifier = source.get("li_universalname", "")
            if identifier and industries:
                asyncio.create_task(
                    insert_company_mapping(company_name, industries, identifier)
                )
            if es_id and source:
                return es_id, source
        except Exception as e:
            traceback.print_exc()
            pass

    # If profile-based search fails, try alternative search methods
    else:
        # Handle company names with accents
        if has_accents(company_name):
            company_name = remove_accents(company_name)

        # Choose search method based on company name characteristics
        es_results = (
            await quad_query_executor(company_name, client)
            if has_special_characters(company_name)
            else await dual_query_executor(company_name, client)
        )

        if es_results:
            # Process results from alternative search
            data_to_transform = [item[1] for item in es_results]
            transformed_data = transform_for_white_death(data_to_transform)
            li_name = await veiled_death(
                prompt, company_name, industries, transformed_data
            )
            source = None
            es_id = None

            if not li_name:
                return None, None
            else:
                # Find the matching company in the results
                for result in data_to_transform:
                    if result.get("li_name", "") == li_name:
                        source = result
                        break
                es_id = next(
                    (
                        item[0]
                        for item in es_results
                        if item[1].get("li_name") == li_name
                    ),
                    None,
                )
                # Cache the successful match
                identifier = source.get("li_universalname", "")
                if identifier and industries:
                    asyncio.create_task(
                        insert_company_mapping(company_name, industries, identifier)
                    )
                if es_id and source:
                    return es_id, source
                else:
                    return None, None
        return None, None
    return None, None


async def white_death_v2(
    prompt, company_name, industries, client, company_mapping_cache=None
):
    """
    Enhanced version of the white_death function with improved caching logic.

    This function is similar to white_death but includes additional logic for handling
    multiple industries and improved caching mechanisms.

    Args:
        prompt (str): The user's original query
        company_name (str): The name of the company to search for
        industries (str): String representation of a list of industries
        client: The Elasticsearch client
        company_mapping_cache (dict, optional): Cache of previously identified companies

    Returns:
        tuple: A tuple containing (es_id, source) or (None, None) if not found
    """
    # Parse industries from string to list
    industries = ast.literal_eval(industries)

    async def insert_company_mapping(company_name, industries, identifier):
        """
        Inserts or updates company mapping in the database.

        This function adds a new mapping between a company name, its industries,
        and its LinkedIn universal name to the database, or updates the count
        if the mapping already exists.

        Args:
            company_name (str): The name of the company
            industries (list): List of industries the company operates in
            identifier (str): The LinkedIn universal name of the company
        """
        if identifier and industries:
            # Sanitize inputs for SQL query
            safe_company_name = company_name.replace("'", "''")
            safe_identifier = identifier.replace("'", "''")

            # Create tuples for each industry
            tuples = [
                f"('{safe_company_name}', '{industry}', 'United States', '{safe_identifier}')"
                for industry in industries
            ]

            # Construct and execute the SQL query
            values_clause = ", ".join(tuples)
            query = f"""
                INSERT INTO company_mapping_universalname (name, industry, location, universal_name)
                VALUES {values_clause}
                ON CONFLICT (name, industry, location) DO UPDATE SET counts = company_mapping_universalname.counts + 1;
            """
            try:
                await postgres_insert(query)
            except Exception as e:
                print(f"Error inserting company mapping into cache: {str(e)}")

    # Prepare query parameters
    query_industries = tuple(industries) if industries else ()
    target_count = 6
    location = "United States"

    # Sanitize company name for SQL query
    safe_company_name = company_name.replace("'", "''")

    # Check cache only if there are multiple industries
    if len(query_industries) > 1:
        cache_hit_query = f"""
                SELECT name, location, total_counts, universal_name
                    FROM (
                        SELECT name, industry, location, universal_name,
                            SUM(counts) OVER (PARTITION BY name, location) AS total_counts
                        FROM company_mapping_universalname
                        WHERE name = '{safe_company_name}'
                        AND location = '{location}'
                        {f'AND industry IN {query_industries}' if query_industries else ''}
                    ) AS subquery
                    WHERE total_counts >= {target_count}
                    GROUP BY name, location, total_counts, universal_name
                    {f'HAVING COUNT(DISTINCT industry) = {len(query_industries)}' if query_industries else ''};
            """
        try:
            # Try to get company from cache
            if company_mapping_cache:
                cache = company_mapping_cache.get((company_name, location), None)
            else:
                cache = await postgres_fetch(cache_hit_query)
            if cache:
                es_id, source = await get_source_for_cache(cache[3], client)
                return es_id, source
        except:
            pass

    # If not in cache, search using profile-based query
    es_results = await profile_query_executor(company_name)
    data_to_transform = [item[1] for item in es_results]
    transformed_data = transform_for_white_death(data_to_transform)
    li_name = await white_guard(prompt, company_name, industries, transformed_data)
    source = None
    es_id = None

    # Process results from profile-based search
    if li_name:
        # Find the matching company in the results
        for result in data_to_transform:
            if result.get("li_name", "").lower().strip() == li_name.lower().strip():
                source = result
                break
        es_id = next(
            (
                item[0]
                for item in es_results
                if item[1].get("li_name").lower().strip() == li_name.lower().strip()
            ),
            None,
        )
        try:
            # Cache the successful match
            identifier = source.get("li_universalname", "")
            if identifier and industries:
                asyncio.create_task(
                    insert_company_mapping(company_name, industries, identifier)
                )
            if es_id and source:
                return es_id, source
        except Exception as e:
            traceback.print_exc()
            pass

    # If profile-based search fails, try alternative search methods
    else:
        # Handle company names with accents
        if has_accents(company_name):
            company_name = remove_accents(company_name)

        # Choose search method based on company name characteristics
        es_results = (
            await quad_query_executor(company_name, client)
            if has_special_characters(company_name)
            else await dual_query_executor(company_name, client)
        )

        if es_results:
            # Process results from alternative search
            data_to_transform = [item[1] for item in es_results]
            transformed_data = transform_for_white_death(data_to_transform)
            li_name = await veiled_death(
                prompt, company_name, industries, transformed_data
            )
            source = None
            es_id = None

            if not li_name:
                return None, None
            else:
                # Find the matching company in the results
                for result in data_to_transform:
                    if result.get("li_name", "") == li_name:
                        source = result
                        break
                es_id = next(
                    (
                        item[0]
                        for item in es_results
                        if item[1].get("li_name") == li_name
                    ),
                    None,
                )
                # Cache the successful match
                identifier = source.get("li_universalname", "")
                if identifier and industries:
                    asyncio.create_task(
                        insert_company_mapping(company_name, industries, identifier)
                    )
                if es_id and source:
                    return es_id, source
                else:
                    return None, None
        return None, None


async def get_matching_documents(
    company_name: str, pool: aiomysql.Pool, limit: int = 150
):
    sql_query = """
        SELECT company_recurrence, WEIGHT() as relevance_score
        FROM flattened_people 
        WHERE MATCH(%s)
        ORDER BY relevance_score DESC
        LIMIT %s;
    """
    params = (company_name, limit)

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql_query, params)
                result = await cur.fetchall()
                return result
    except aiomysql.MySQLError as exception:
        print("MYSQL ERROR", exception)
        return []
    except Exception as exception:
        print("EXCEPTION", exception)
        return []


def create_company_recurrence_hashmap(documents):
    company_counts = defaultdict(int)
    strings_to_process = [document[0] for document in documents]
    for entry in strings_to_process:
        companies_in_entry = entry.split(",")
        for company_str in companies_in_entry:
            parts = company_str.strip().split(":")
            if len(parts) == 2:
                name = parts[0].strip()
                try:
                    count = int(parts[1].strip())
                    if count > 0:
                        company_counts[name] += count
                except ValueError:
                    continue

    sorted_company_items = sorted(
        company_counts.items(), key=lambda item: item[1], reverse=True
    )
    top_10_companies = sorted_company_items[:10]

    recurrence_hashmap = {
        company_name: math.log(count)
        for company_name, count in top_10_companies
        if math.log(count) != 0
    }
    return recurrence_hashmap


async def get_company_details(company_name, recurrence_hashmap, client, locations=None):
    tokens = company_name.split()
    num_tokens = len(tokens)

    min_should_match = 2 if num_tokens >= 2 else 1

    if num_tokens >= 2:
        second_bool_should = []
        for token in tokens:
            fuzziness = 2 if len(token) > 5 else 1
            token_matches = {
                "bool": {
                    "should": [
                        {
                            "match": {
                                "li_description": {
                                    "query": token.lower(),
                                    "fuzziness": fuzziness,
                                }
                            }
                        },
                        {
                            "match": {
                                "li_name": {
                                    "query": token.lower(),
                                    "fuzziness": fuzziness,
                                }
                            }
                        },
                        {
                            "match": {
                                "cb_full_description": {
                                    "query": token.lower(),
                                    "fuzziness": fuzziness,
                                }
                            }
                        },
                    ],
                    "minimum_should_match": 1,
                }
            }
            second_bool_should.append(token_matches)
    else:
        fuzziness = 2 if len(company_name) > 5 else 1
        second_bool_should = [
            {
                "match": {
                    "li_name": {"query": company_name.lower(), "fuzziness": fuzziness}
                }
            },
            {
                "match": {
                    "li_description": {
                        "query": company_name.lower(),
                        "fuzziness": fuzziness,
                    }
                }
            },
            {
                "match": {
                    "cb_full_description": {
                        "query": company_name.lower(),
                        "fuzziness": fuzziness,
                    }
                }
            },
        ]

    base_must_clauses = []

    if recurrence_hashmap:
        base_must_clauses.append(
            {
                "bool": {
                    "should": [
                        {
                            "match": {
                                "li_universalname": {
                                    "query": key,
                                    "boost": recurrence_hashmap[key],
                                }
                            }
                        }
                        for key in recurrence_hashmap
                    ],
                    "minimum_should_match": 1,
                }
            }
        )

    base_must_clauses.append(
        {
            "bool": {
                "should": second_bool_should,
                "minimum_should_match": min_should_match,
            }
        }
    )

    location_clauses = []
    if locations and isinstance(locations, dict):
        locations_list = locations.get("location", [])

        for loc in locations_list:
            location_should_clauses = []

            headquarter_sub_clauses = []
            if loc.get("country"):
                headquarter_sub_clauses.append(
                    {
                        "match_phrase": {
                            "li_headquarter.country.keyword": {"query": loc["country"]}
                        }
                    }
                )
            if loc.get("state"):
                headquarter_sub_clauses.append(
                    {
                        "match_phrase": {
                            "li_headquarter.geographicArea.keyword": {
                                "query": loc["state"]
                            }
                        }
                    }
                )
            if loc.get("city"):
                headquarter_sub_clauses.append(
                    {
                        "match_phrase": {
                            "li_headquarter.city.keyword": {"query": loc["city"]}
                        }
                    }
                )

            if headquarter_sub_clauses:
                location_should_clauses.append(
                    {
                        "nested": {
                            "path": "li_headquarter",
                            "query": {
                                "bool": {
                                    "should": headquarter_sub_clauses,
                                    "minimum_should_match": 1,
                                }
                            },
                        }
                    }
                )

            confirmed_sub_clauses = []
            if loc.get("country"):
                confirmed_sub_clauses.append(
                    {
                        "match_phrase": {
                            "li_confirmedlocations.country": {"query": loc["country"]}
                        }
                    }
                )
            if loc.get("state"):
                confirmed_sub_clauses.append(
                    {
                        "match_phrase": {
                            "li_confirmedlocations.geographicArea": {
                                "query": loc["state"]
                            }
                        }
                    }
                )
            if loc.get("city"):
                confirmed_sub_clauses.append(
                    {
                        "match_phrase": {
                            "li_confirmedlocations.city": {"query": loc["city"]}
                        }
                    }
                )

            if confirmed_sub_clauses:
                location_should_clauses.append(
                    {
                        "nested": {
                            "path": "li_confirmedlocations",
                            "query": {
                                "bool": {
                                    "should": confirmed_sub_clauses,
                                    "minimum_should_match": 1,
                                }
                            },
                        }
                    }
                )

            if location_should_clauses:
                location_clauses.append(
                    {
                        "bool": {
                            "should": location_should_clauses,
                            "minimum_should_match": 1,
                        }
                    }
                )

    must_clauses_with_location = base_must_clauses.copy()
    if location_clauses:
        if len(location_clauses) == 1:
            must_clauses_with_location.append(location_clauses[0])
        else:
            must_clauses_with_location.append(
                {"bool": {"should": location_clauses, "minimum_should_match": 1}}
            )

    search_body_template = {
        "_source": [
            "li_universalname",
            "li_name",
            "li_industries",
            "li_specialties",
            "li_size",
            "li_urn",
        ],
        "size": 3,
    }

    searches_to_run = []

    if location_clauses:
        search_with_location = client.search(
            index="company",
            body={
                **search_body_template,
                "query": {"bool": {"must": must_clauses_with_location}},
            },
        )
        searches_to_run.append(search_with_location)

    search_without_location = client.search(
        index="company",
        body={
            **search_body_template,
            "query": {"bool": {"must": base_must_clauses}},
        },
    )
    searches_to_run.append(search_without_location)

    if num_tokens >= 2:
        acronym = "".join([token[0].upper() for token in tokens])
        acronym_search = client.search(
            index="company",
            body={
                "_source": [
                    "li_universalname",
                    "li_name",
                    "li_industries",
                    "li_specialties",
                    "li_size",
                    "li_urn",
                ],
                "size": 1,
                "query": {
                    "bool": {
                        "must": [
                            {"match_phrase": {"li_name": acronym.lower()}},
                        ]
                    }
                },
            },
        )
        searches_to_run.append(acronym_search)

    search_results = await asyncio.gather(*searches_to_run)

    combined_hits = []
    for result in search_results:
        combined_hits.extend(result["hits"]["hits"])

    seen_urns = set()
    unique_hits = []
    for hit in combined_hits:
        urn = hit["_source"].get("li_urn")
        if urn not in seen_urns:
            seen_urns.add(urn)
            unique_hits.append(hit)

    companies = {"hits": {"hits": unique_hits, "total": {"value": len(unique_hits)}}}

    return companies


def preprocess_company_details(companies):
    payload = {}
    NOT_AVAILABLE_MSG = "NOT AVAILABLE"
    hits_container = companies.get("hits", {})
    actual_hits = hits_container.get("hits", [])
    for hit in actual_hits:
        source = hit.get("_source", {})
        universal_name = source.get("li_universalname")
        if not universal_name:
            continue
        name = source.get("li_name", NOT_AVAILABLE_MSG)
        industries = source.get("li_industries", [])
        if not isinstance(industries, list):
            industries = []
        specialties = source.get("li_specialties", [])
        if not isinstance(specialties, list):
            specialties = []
        combined_industries = industries + specialties
        raw_size = source.get("li_size")
        size = NOT_AVAILABLE_MSG
        if raw_size is not None:
            try:
                size = int(raw_size)
            except (ValueError, TypeError):
                size = NOT_AVAILABLE_MSG
        payload[universal_name] = {
            "name": name,
            "industries": combined_industries,
            "size": size,
        }
    return payload


def extract_actual_url(redirect_url):
    """
    Extract the actual URL from various search engine redirect URLs
    Supports Yahoo, Google, Bing, and other common redirect patterns
    """

    yahoo_match = re.search(r"RU=([^/&]+)", redirect_url)
    if yahoo_match:
        encoded_url = yahoo_match.group(1)
        try:
            decoded_url = urllib.parse.unquote(encoded_url)
            return decoded_url
        except:
            pass

    google_match = re.search(r"[?&]url=([^&]+)", redirect_url)
    if google_match:
        encoded_url = google_match.group(1)
        try:
            decoded_url = urllib.parse.unquote(encoded_url)
            return decoded_url
        except:
            pass

    bing_match = re.search(r"[?&]r=([^&]+)", redirect_url)
    if bing_match:
        encoded_url = bing_match.group(1)
        try:
            decoded_url = urllib.parse.unquote(encoded_url)
            return decoded_url
        except:
            pass

    url_patterns = [r"url=([^&]+)", r"RU=([^&/]+)", r"q=([^&]+)", r"target=([^&]+)"]

    for pattern in url_patterns:
        match = re.search(pattern, redirect_url, re.IGNORECASE)
        if match:
            potential_url = urllib.parse.unquote(match.group(1))
            if potential_url.startswith(("http://", "https://")):
                return potential_url
    return redirect_url


async def company_mapping(
    user_query, relevant_industries, company_name, potential_companies
):
    retries = 3
    potential_keys = list(potential_companies.keys())
    if len(potential_keys) == 0:
        return None

    for _ in range(retries):
        response = await invoke(
            messages=[
                {
                    "role": "system",
                    "content": COMPANY_MAPPING_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": f"""
User Query: "{user_query}"
Industries: "{relevant_industries}"
Company Name: "{company_name}"

The potential companies are:
    {potential_companies}
""",
                },
            ],
            model="groq/openai/gpt-oss-20b",
            temperature=0,
            fallbacks=["groq/llama-3.3-70b-versatile", "openai/gpt-4.1-mini"],
        )
        match = re.search(r"<answer>(.*?)</answer>", response)
        answer = match.group(1) if match else None
        if answer in potential_keys or answer == "NONE":
            return answer
    return None


async def background_company_mapping_ingestion(
    company_name,
    user_query,
    valid_industries,
    cache_value_keys,
    cache_count_keys,
    elasticsearch_client,
    redis_client,
):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                os.getenv("CLOUDFUNCTION_SERVICE"),
                params={
                    "query": f"site:linkedin.com/company/ {company_name}",
                    "search_engine": "yahoo",
                    "js_enabled": "false",
                    "caching_enabled": "true",
                    "low_memory": "true",
                },
                headers={"accept": "application/json"},
            ) as response:
                response.raise_for_status()
                google_response = await response.json()
                universal_name = extract_actual_url(
                    google_response["query_result"][0]["link"]
                ).split("/")[-1]
                potential_companies = await elasticsearch_client.search(
                    index="company",
                    body={
                        "_source": [
                            "li_universalname",
                            "li_name",
                            "li_industries",
                            "li_specialties",
                            "li_size",
                            "li_urn",
                        ],
                        "size": 1,
                        "query": {"match": {"li_universalname": universal_name}},
                    },
                )
                potential_companies_data = preprocess_company_details(
                    potential_companies
                )
                correct_company = await company_mapping(
                    user_query, valid_industries, company_name, potential_companies_data
                )
                hits_container = potential_companies.get("hits", {})
                actual_hits = hits_container.get("hits", [])

                for hit in actual_hits:
                    source = hit.get("_source", {})
                    universal_name = source.get("li_universalname")
                    if universal_name == correct_company:
                        es_id = hit.get("_id")

                        pipeline = redis_client.pipeline()
                        for val_key, count_key in zip(
                            cache_value_keys, cache_count_keys
                        ):
                            pipeline.set(val_key, f"{es_id}~{json.dumps(source)}")
                            pipeline.incr(count_key)

                        await pipeline.execute()
                        return es_id, source
    except:
        return None, None


async def map_company(
    company_name,
    user_query,
    relevant_industries,
    elasticsearch_client,
    mysql_pool,
    redis_client,
    count_threshold=3,
    locations=None,
):
    try:
        if not relevant_industries:
            valid_industries = ["No Industry"]
        else:
            valid_industries = [ind for ind in relevant_industries if ind]

        environment = os.getenv("ENVIRONMENT")

        cache_value_keys = [
            f"{environment}-{company_name}-{industry}-value"
            for industry in valid_industries
        ]
        cache_count_keys = [
            f"{environment}-{company_name}-{industry}-count"
            for industry in valid_industries
        ]

        pipeline = redis_client.pipeline()

        for key in cache_count_keys:
            pipeline.get(key)
        for key in cache_value_keys:
            pipeline.get(key)

        results = await pipeline.execute()

        counts = results[: len(cache_count_keys)]
        cached_values = results[len(cache_count_keys) :]

        counts = [int(c) if c is not None else 0 for c in counts]

        if all(c >= count_threshold for c in counts) and all(
            val is not None for val in cached_values
        ):
            try:
                val = cached_values[0]
                es_id, source_json = val.split("~", 1)
                source = json.loads(source_json)
                return es_id, source
            except Exception as e:
                print("cache parse error", e)
                pass

        matching_documents = await get_matching_documents(company_name, mysql_pool)
        recurrence_hashmap = create_company_recurrence_hashmap(matching_documents)
        potential_companies = await get_company_details(
            company_name, recurrence_hashmap, elasticsearch_client, locations
        )
        potential_companies_data = preprocess_company_details(potential_companies)

        correct_company = await company_mapping(
            user_query, valid_industries, company_name, potential_companies_data
        )

        if correct_company == "NONE" or correct_company is None:
            asyncio.create_task(
                background_company_mapping_ingestion(
                    company_name,
                    user_query,
                    valid_industries,
                    cache_value_keys,
                    cache_count_keys,
                    elasticsearch_client,
                    redis_client,
                )
            )
            return None, None

        hits_container = potential_companies.get("hits", {})
        actual_hits = hits_container.get("hits", [])

        for hit in actual_hits:
            source = hit.get("_source", {})
            universal_name = source.get("li_universalname")
            if universal_name == correct_company:
                es_id = hit.get("_id")

                pipeline = redis_client.pipeline()
                for val_key, count_key in zip(cache_value_keys, cache_count_keys):
                    pipeline.set(val_key, f"{es_id}~{json.dumps(source)}")
                    pipeline.incr(count_key)

                asyncio.create_task(pipeline.execute())

                return es_id, source

        return None, None
    except Exception as exception:
        print("Exception in map_company", exception)
        traceback.print_exc()
        return None, None
