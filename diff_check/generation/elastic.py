import os
import math
import asyncio
import traceback
from collections import defaultdict
from app.utils.search.aisearch.company.generation.utilities import (
    replace_special_characters_with_space,
    replace_special_characters_with_blank,
)


async def get_source_for_cache(li_universalname, client):
    """
    Retrieves company data from Elasticsearch using the LinkedIn universal name.

    This function searches for a company in Elasticsearch using its LinkedIn universal name
    and returns the company's ID and source data.

    Args:
        li_universalname (str): The LinkedIn universal name of the company
        client: The Elasticsearch client

    Returns:
        tuple: A tuple containing (es_id, source) or (None, None) if not found
    """
    query = {
        "_source": [
            "li_universalname",
            "li_name",
            "li_urn",
            "li_specialties",
            "li_industries",
            "li_description",
            "li_size",
            "li_staffcount",
        ],
        "query": {"term": {"li_universalname": {"value": li_universalname}}},
    }

    try:
        es_result = await client.search(
            index=os.getenv("ES_COMPANIES_INDEX"), body=query
        )
        source = es_result["hits"]["hits"][0]["_source"]
        es_id = es_result["hits"]["hits"][0]["_id"]
        return es_id, source
    except:
        pass
    return None


async def profile_query_executor(company_name):
    """
    Executes a profile-based query to find companies in Elasticsearch.

    This function searches for companies by analyzing profile data in Elasticsearch.
    It first searches for profiles that mention the company name, then uses the
    universal names found in those profiles to search for companies.

    Args:
        company_name (str): The name of the company to search for

    Returns:
        list: A list of tuples containing (es_id, source) for matching companies
    """
    from elasticsearch import AsyncElasticsearch

    # Create a connection to Elasticsearch
    connection = AsyncElasticsearch(
        hosts=os.getenv("ES_URL"),
        api_key=(os.getenv("ES_ID"), os.getenv("ES_KEY")),
        request_timeout=30,
        max_retries=5,
        retry_on_timeout=True,
    )

    # Normalize the company name for searching
    company_name = (
        company_name.replace(".", " ").replace("-", " ").replace("'", " ").lower()
    )
    base_company = company_name

    # Query to find profiles that mention the company
    query = {
        "size": 150,
        "_source": ["experience.company_universal_name"],
        "query": {
            "bool": {
                "should": [
                    {
                        "nested": {
                            "path": "experience",
                            "query": {
                                "bool": {
                                    "should": [
                                        {"match": {"experience.title": company_name}},
                                        {
                                            "match": {
                                                "experience.job_summary": company_name
                                            }
                                        },
                                        {
                                            "match": {
                                                "experience.company_description": company_name
                                            }
                                        },
                                        {
                                            "match": {
                                                "experience.company_name": company_name
                                            }
                                        },
                                    ],
                                    "minimum_should_match": 2,
                                }
                            },
                        }
                    },
                    {"match": {"headline": company_name}},
                    {"match": {"summary": company_name}},
                ],
                "minimum_should_match": 1,
            }
        },
    }

    # Execute the profile search query
    results = await connection.search(
        body=query, index=os.getenv("ES_PROFILES_INDEX"), timeout="60s"
    )
    results = results["hits"]["hits"]

    # Count occurrences of each universal name in the profiles
    universal_names = defaultdict(int)

    for r in results:
        try:
            for exp in r["_source"]["experience"]:
                company_name = exp.get("company_universal_name")
                if company_name:
                    universal_names[company_name] += 1
        except Exception:
            pass

    # Apply logarithmic scaling to the counts
    company_data = {
        key: math.log(value)
        for key, value in dict(
            sorted(universal_names.items(), key=lambda item: item[1], reverse=True)[:10]
        ).items()
    }

    # Query to find companies using the universal names found in profiles
    query = {
        "_source": [
            "li_universalname",
            "li_name",
            "li_urn",
            "li_specialties",
            "li_industries",
            "li_description",
            "li_staffcount",
            "li_size",
            "li_confirmedlocations",
        ],
        "query": {
            "bool": {
                "must": [
                    {
                        "bool": {
                            "should": [
                                {
                                    "match": {
                                        "li_universalname": {
                                            "query": key,
                                            "boost": company_data[key],
                                        }
                                    }
                                }
                                for key in company_data
                            ],
                            "minimum_should_match": 1,
                        }
                    },
                    {
                        "bool": {
                            "should": [
                                {
                                    "match": {
                                        "li_name": {
                                            "query": base_company,
                                            "fuzziness": "1",
                                        }
                                    }
                                },
                                {
                                    "match": {
                                        "li_description": {
                                            "query": base_company,
                                            "fuzziness": "1",
                                        }
                                    }
                                },
                            ],
                            "minimum_should_match": 1,
                        }
                    },
                ]
            }
        },
    }

    # Execute the company search query
    companies_data = await connection.search(
        body=query, index=os.getenv("ES_COMPANIES_INDEX"), timeout="60s"
    )

    await connection.close()

    # Process the results
    results = []
    for data in companies_data["hits"]["hits"]:
        try:
            results.append((data["_id"], data["_source"]))
        except Exception as e:
            traceback.print_exc()
            pass
        if len(results) == 3:
            break

    return results


async def quad_query_executor(company_name, client):
    """
    Executes four different queries to find companies in Elasticsearch.

    This function performs four different searches for a company in Elasticsearch,
    using different combinations of name formats and sorting options. It then
    combines and deduplicates the results.

    Args:
        company_name (str): The name of the company to search for
        client: The Elasticsearch client

    Returns:
        list: A list of tuples containing (es_id, source) for matching companies
    """
    # Prepare different formats of the company name
    name_with_space = replace_special_characters_with_space(company_name)
    name_with_blank = replace_special_characters_with_blank(company_name)

    # Base query structure
    base_query = {
        "_source": [
            "li_universalname",
            "li_name",
            "li_urn",
            "li_specialties",
            "li_industries",
            "li_description",
            "li_size",
            "li_staffcount",
        ],
        "size": 5,
    }

    # Define four different queries with varying parameters
    queries = [
        {
            **base_query,
            "query": {
                "bool": {
                    "must": [
                        {"match": {"li_name": {"query": name_with_space, "boost": 2}}}
                    ],
                    "should": [{"match": {"li_universalname": name_with_space}}],
                }
            },
            "sort": [{"li_size": {"order": "desc"}}],
        },
        {
            **base_query,
            "query": {
                "bool": {
                    "must": [
                        {"match": {"li_name": {"query": name_with_space, "boost": 2}}}
                    ],
                    "should": [{"match": {"li_universalname": name_with_space}}],
                }
            },
        },
        {
            **base_query,
            "query": {
                "bool": {
                    "must": [
                        {"match": {"li_name": {"query": name_with_blank, "boost": 2}}}
                    ],
                    "should": [{"match": {"li_universalname": name_with_blank}}],
                }
            },
            "sort": [{"li_size": {"order": "desc"}}],
        },
        {
            **base_query,
            "query": {
                "bool": {
                    "must": [
                        {"match": {"li_name": {"query": name_with_blank, "boost": 2}}}
                    ],
                    "should": [{"match": {"li_universalname": name_with_blank}}],
                }
            },
        },
    ]

    # Execute all queries concurrently
    tasks = [
        client.search(index=os.getenv("ES_COMPANIES_INDEX"), body=query)
        for query in queries
    ]
    responses = await asyncio.gather(*tasks)

    # Combine results from all queries
    combined_responses = []
    for response in responses:
        combined_responses.extend(response["hits"]["hits"][:3])

    # Deduplicate results based on universal name or company name
    unique_response = {}
    for doc in combined_responses:
        unique_key = doc["_source"].get("li_universalname") or doc["_source"].get(
            "li_name"
        )
        if unique_key:
            unique_response[unique_key] = doc

    # Format the results
    results = []
    for data in list(unique_response.values()):
        try:
            results.append((data["_id"], data["_source"]))
        except Exception as e:
            traceback.print_exc()
            print(e)
    return results


async def dual_query_executor(company_name, client):
    """
    Executes two different queries to find companies in Elasticsearch.

    This function performs two different searches for a company in Elasticsearch,
    one with sorting by company size and one without. It then combines and
    deduplicates the results.

    Args:
        company_name (str): The name of the company to search for
        client: The Elasticsearch client

    Returns:
        list: A list of tuples containing (es_id, source) for matching companies
    """
    # Base query structure
    query = {
        "_source": [
            "li_universalname",
            "li_name",
            "li_urn",
            "li_specialties",
            "li_industries",
            "li_description",
            "li_size",
            "li_staffcount",
        ],
        "query": {
            "bool": {
                "must": [{"match": {"li_name": {"query": company_name, "boost": 2}}}],
                "should": [{"match": {"li_universalname": company_name}}],
            }
        },
    }

    # Create a copy of the query with sorting by company size
    query_with_sort = query.copy()
    query_with_sort["sort"] = [{"li_size": {"order": "desc"}}]

    # Execute both queries concurrently
    tasks = [
        client.search(index=os.getenv("ES_COMPANIES_INDEX"), body=query_with_sort),
        client.search(index=os.getenv("ES_COMPANIES_INDEX"), body=query),
    ]
    responses = await asyncio.gather(*tasks)

    # Combine results from both queries
    combined_responses = (
        responses[0]["hits"]["hits"][:3] + responses[1]["hits"]["hits"][:3]
    )

    # Deduplicate results based on universal name or company name
    unique_response = {}
    for doc in combined_responses:
        unique_key = doc["_source"].get("li_universalname") or doc["_source"].get(
            "li_name"
        )
        if unique_key:
            unique_response[unique_key] = doc

    # Format the results
    results = []
    for data in list(unique_response.values()):
        try:
            results.append((data["_id"], data["_source"]))
        except Exception as e:
            traceback.print_exc()
            print(e)
    return results


async def get_company_source(es_id, source):
    """
    Extracts relevant company information from Elasticsearch source data.

    This function processes the raw source data from Elasticsearch and extracts
    the most relevant company information in a standardized format.

    Args:
        es_id (str): The Elasticsearch document ID
        source (dict): The source data from Elasticsearch

    Returns:
        dict: A dictionary containing standardized company information or None if processing fails
    """
    try:
        # Extract relevant fields from the source data
        name = source.get("li_name", "")
        li_urn = source.get("li_urn", "")
        employCount = source.get("li_staffcount", source.get("li_size", 0))
        li_industries = source.get("li_industries", [])
        industry = li_industries[0] if li_industries else ""
        universal_name = source.get("li_universalname", "")

        # Return standardized company information
        return {
            "es_id": es_id,
            "name": name,
            "urn": li_urn,
            "universalName": universal_name,
            "employCount": employCount,
            "industry": industry,
        }
    except Exception as exception:
        print(f"Error processing company source: {exception}")
        return None
