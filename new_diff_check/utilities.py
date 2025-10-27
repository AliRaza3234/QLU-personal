import os
import re
import ast
import json
import urllib
import aiohttp
import asyncio
import unicodedata

from qutils.llm.asynchronous import invoke
from app.core.database import postgres_fetch, postgres_insert, postgres_fetch_all
from app.utils.search.aisearch.company.generation.p2p import enqueue


def extract_json(data):
    """
    Extracts a JSON object from a string that may contain other content.

    This function finds the first '{' and last '}' in the string and extracts
    the JSON object between them.

    Args:
        data (str): String containing a JSON object

    Returns:
        dict: The extracted JSON object
    """
    return json.loads(data[data.find("{") : data.rfind("}") + 1])


def has_special_characters(text):
    """
    Checks if a string contains any special characters.

    Args:
        text (str): The string to check

    Returns:
        bool: True if the string contains special characters, False otherwise
    """
    return bool(re.search(r"[^a-zA-Z0-9\s]", text))


def replace_special_characters_with_space(text):
    """
    Replaces all special characters in a string with spaces.

    Args:
        text (str): The string to process

    Returns:
        str: The string with special characters replaced by spaces
    """
    return re.sub(r"[^a-zA-Z0-9]", " ", text)


def replace_special_characters_with_blank(text):
    """
    Removes all special characters from a string.

    Args:
        text (str): The string to process

    Returns:
        str: The string with all special characters removed
    """
    return re.sub(r"[^a-zA-Z0-9]", "", text)


def has_accents(input_str):
    """
    Checks if a string contains any accented characters.

    Args:
        input_str (str): The string to check

    Returns:
        bool: True if the string contains accented characters, False otherwise
    """
    for char in input_str:
        if char != unicodedata.normalize("NFD", char)[0]:
            return True
    return False


def remove_accents(input_str):
    """
    Removes all accents from a string and replaces special characters with spaces.

    Args:
        input_str (str): The string to process

    Returns:
        str: The string with accents removed and special characters replaced by spaces
    """
    # Normalize the string to decompose accented characters
    normalized = unicodedata.normalize("NFKD", input_str)
    # Encode to ASCII, ignoring non-ASCII characters, then decode back to string
    ascii_str = normalized.encode("ASCII", "ignore").decode("ASCII")
    # Replace any remaining special characters with spaces
    cleaned_str = re.sub(r"[^a-zA-Z0-9\s]", " ", ascii_str)
    # Normalize whitespace (replace multiple spaces with a single space)
    cleaned_str = " ".join(cleaned_str.split())
    return cleaned_str


def post_process_gpt_output(response):
    """
    Extracts the content between XML-like tags from a GPT response.

    This function extracts the content between the last set of tags in the response.

    Args:
        response (str): The raw response from GPT

    Returns:
        str: The extracted content
    """
    return (
        response[response[: response.rfind("<")].rfind("<") :]
        .split("<")[1]
        .split(">")[1]
        .strip()
    )


async def cache_industry(prompt):
    """
    Identifies relevant industries for a user query and caches company data.

    This function uses an LLM to identify industries relevant to the user's query,
    then queries the database to find companies in those industries and caches them.

    Args:
        prompt (str): The user's input prompt

    Returns:
        tuple: A tuple containing (industries_list, cached_companies_hashmap)
    """
    # Format the user prompt for the LLM
    user_prompt = f"""
            <Task>
                - Based on the user query: "{prompt}" give me a list of industries that would be relevant for finding such companies.
                - Make sure to only generate 1 to 3 industries which are the most relevant to look at.
                - The amount is dependant on the open ended nature of the query, if more are required to cover the query you may generate more.
                - If only a company is mentioned that you dont know in the prompt, return an empty list.
            </Task>

            <Output>
                - First give your thought process in one line then give the list of industries.
                - Give your output in the form <prediction>["industry 1", "industry 2", ...]</prediction>.
            </Output>
        """

    # Call the LLM to identify relevant industries
    response = await invoke(
        messages=[
            {
                "role": "system",
                "content": "You are a relevant industry name generating agent.",
            },
            {"role": "user", "content": user_prompt},
        ],
        model="groq/llama-3.3-70b-versatile",
        temperature=0,
        fallbacks=["openai/gpt-4.1"],
    )

    # Process the response to extract the list of industries
    response = post_process_gpt_output(response)

    industries = ast.literal_eval(response)
    query_industries = tuple(industries)
    target_count = 6

    # Build and execute the SQL query to find companies in the identified industries
    query = f"""
    WITH filtered_companies AS (
        SELECT
            name,
            location,
            universal_name,
            counts
        FROM
            company_mapping_universalname
        WHERE
            {f"industry IN {query_industries}" if query_industries else "1=1"}
    )
    SELECT
        name,
        location,
        SUM(counts) AS total_counts,
        universal_name
    FROM
        filtered_companies
    GROUP BY
        name, location, universal_name
    HAVING
        SUM(counts) >= {target_count}
        {f"AND COUNT(*) >= 2" if query_industries and len(query_industries) == 3 else f"AND COUNT(*) = {len(query_industries)}" if query_industries else ""};
    """

    global_cache = await postgres_fetch_all(query)
    # Create a hashmap of the cached companies for quick lookup
    hashmap = {}

    if global_cache:
        for i in global_cache:
            hashmap[(i[0], i[1])] = i

    return response, hashmap


def process_line(line):
    line = line.strip()
    match = re.search(r"^\d+\.\s*(.*)", line)
    if match:
        name = match.group(1)
        return name
    else:
        return None


async def search_with_proxy_async(
    name,
    client,
    search_engine="google",
    js_enabled=True,
    caching_enabled=True,
    low_memory=False,
):
    """
    Searches for a company's LinkedIn identifier using a proxy service.

    This function searches for a company on LinkedIn using a proxy service
    and extracts the company's LinkedIn identifier. It also caches the result
    for future use.

    Args:
        name (str or tuple): The company name to search for
        client: The Elasticsearch client
        search_engine (str, optional): The search engine to use, defaults to "google"
        js_enabled (bool, optional): Whether to enable JavaScript, defaults to True
        caching_enabled (bool, optional): Whether to enable caching, defaults to True
        low_memory (bool, optional): Whether to use low memory mode, defaults to False

    Returns:
        str: The company's LinkedIn identifier or None if not found
    """
    if not name:
        return {"error": "Empty name provided"}

    # Normalize the company name
    name_str = (
        str(name[0]).replace("'", "")
        if isinstance(name, (list, tuple))
        else str(name).replace("'", "")
    )

    # Check if the result is already cached
    cache_id = f"{name_str}~United States"
    cache_result = await postgres_fetch(
        f"SELECT * FROM google_universal_names WHERE id='{cache_id}'"
    )
    if cache_result:
        return cache_result[1]
    else:
        try:
            top_identifiers = []

            # Make a request to the proxy service
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    os.getenv("CLOUDFUNCTION_SERVICE"),
                    params={
                        "query": f"site:linkedin.com/company/ {name_str}",
                        "search_engine": search_engine,
                        "js_enabled": str(js_enabled).lower(),
                        "caching_enabled": str(caching_enabled).lower(),
                        "low_memory": str(low_memory).lower(),
                    },
                    headers={"accept": "application/json"},
                ) as response:
                    response.raise_for_status()
                    google_response = await response.json()

                    # Extract the LinkedIn identifier from the first result
                    if "?trk" not in google_response["query_result"][0]["link"]:
                        linkedin_url = urllib.parse.unquote(
                            google_response["query_result"][0]["link"]
                        )
                        identifier = (
                            linkedin_url.split("/")[4]
                            if len(linkedin_url.split("/")) > 4
                            else None
                        )
                    else:
                        linkedin_url = urllib.parse.unquote(
                            google_response["query_result"][0]["link"]
                        )
                        identifier = linkedin_url.split("/")[4].split("?trk")[0].strip()

                    # Cache the result for future use
                    asyncio.create_task(
                        postgres_insert(
                            f"INSERT INTO google_universal_names VALUES ('{cache_id}', '{identifier}') ON CONFLICT DO NOTHING"
                        )
                    )

                    # Extract identifiers from the top 5 results
                    for i in range(min(5, len(google_response["query_result"]))):
                        result = google_response["query_result"][i]
                        linkedin_url = urllib.parse.unquote(result["link"])

                        if "?trk" not in linkedin_url:
                            curr_identifier = (
                                linkedin_url.split("/")[4]
                                if len(linkedin_url.split("/")) > 4
                                else None
                            )
                        else:
                            curr_identifier = (
                                linkedin_url.split("/")[4].split("?trk")[0].strip()
                            )

                        if curr_identifier:
                            top_identifiers.append(curr_identifier)

                    # Enqueue the identifiers for further processing
                    await enqueue(top_identifiers, client)

                    return identifier
        except:
            return None


async def insert_company_mapping(company_name, industries, identifier):
    """
    Inserts a company mapping into the database.

    This function creates a mapping between a company name, its industries,
    and its LinkedIn identifier, and inserts it into the database.

    Args:
        company_name (str): The name of the company
        industries (list): List of industries the company belongs to
        identifier (str): The company's LinkedIn identifier

    Returns:
        None
    """
    if identifier and industries:
        # Escape single quotes in the company name and identifier
        safe_company_name = company_name.replace("'", "''")
        safe_identifier = identifier.replace("'", "''")

        # Create tuples for each industry
        tuples = [
            f"('{safe_company_name}', '{industry}', 'United States', '{safe_identifier}')"
            for industry in industries
        ]

        # Build and execute the SQL query
        values_clause = ", ".join(tuples)
        query = f"""
            INSERT INTO company_mapping_universalname (name, industry, location, universal_name)
            VALUES {values_clause}
            ON CONFLICT (name, industry, location) DO UPDATE SET counts = company_mapping_universalname.counts + 1;
        """
        try:
            await postgres_insert(query)
        except:
            pass


async def ownership_checker(company_ownership, es_client):
    data = await es_client.search(
        index="company_ownership",
        body={"query": {"ids": {"values": company_ownership}}},
    )
    hits = data.get("hits", {}).get("hits", [])
    if not hits:
        return None
    source = hits[0].get("_source", {})
    return source.get("company_universal_name")
