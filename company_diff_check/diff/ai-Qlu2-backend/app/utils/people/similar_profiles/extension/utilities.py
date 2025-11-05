import os
import re
import ast
import json
import httpx
import urllib
import asyncio
from app.utils.people.similar_profiles.extension.prompts import (
    GET_BASE_PRODUCT_SYSTEM_PROMPT,
    GET_BASE_PRODUCT_USER_PROMPT,
    FUNCTION_KEYWORDS_SYSTEM_PROMPT,
    FUNCTION_KEYWORDS_USER_PROMPT,
    GET_SIMILAR_COMPANIES_SYSTEM_PROMPT,
    GET_SIMILAR_COMPANIES_WITH_KEYWORDS_USER_PROMPT,
    GET_SIMILAR_COMPANIES_WITHOUT_KEYWORDS_USER_PROMPT,
    NORMALIZE_TITLE_SYSTEM_PROMPT,
    NORMALIZE_TITLE_USER_PROMPT,
    SIMILAR_REIGOINS_USER_PROMPT,
    SIMILAR_REIGOINS_SYSTEM_PROMPT,
    VALIDATOR_AGENT_USER_PROMPT,
    VALIDATOR_AGENT_SYSTEM_PROMPT,
)

from qutils.llm.asynchronous import invoke
from qutils.database.post_gres import postgres_fetch_profile_data


def filter_dict_by_value_range(d, N):
    return {k: v for k, v in d.items() if N - 5 <= v <= N + 5}


def extract_and_decode_url(encoded_url):
    parts = encoded_url.split("/")
    for part in parts:
        if part.startswith("RU="):
            encoded_part = part[3:]
            decoded_url = urllib.parse.unquote(encoded_part)
            return decoded_url
    return "Invalid URL"


async def get_linkedin_identifier(company_name):
    search_term = f"LinkedIn page of company: {company_name}"
    google_response = await get_from_pegasus(search_term)
    search_engine = google_response["search_engine"]
    li_name = None
    if google_response and "query_result" in google_response:
        response = google_response

        for element in response.get("query_result"):
            link_extracted = element["link"]
            if search_engine == "yahoo":
                link_extracted = extract_and_decode_url(link_extracted)
            if "linkedin.com/company" in link_extracted:
                li_name = link_extracted.split("/company/")[-1].split("/")[0]
                if "?" in li_name:
                    li_name = li_name.split("?")[0]
                return li_name

        return li_name


async def get_company_size(li_universalname, client):
    query = {
        "_source": ["li_size"],
        "query": {"match": {"li_universalname": li_universalname}},
    }

    response = await client.search(index="company", body=query)

    hits = response.get("hits", {}).get("hits", [])
    if hits:
        return hits[0]["_source"]
    else:
        return None


async def get_from_pegasus(prompt):
    url = os.getenv("CLOUDFUNCTION_SERVICE")
    headers = {"accept": "application/json"}
    search_engines = ["google", "yahoo"]
    retries = 3
    delay = 1.5

    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(retries):
            for search_engine in search_engines:
                params = {"query": prompt}
                try:
                    response = await client.get(url, headers=headers, params=params)
                    response.raise_for_status()
                    json_response = response.json()
                    return json_response
                except httpx.HTTPStatusError as http_err:
                    status_code = http_err.response.status_code
                    print(
                        f"Attempt {attempt + 1} - Status code: {status_code} with search engine {search_engine}"
                    )
                except httpx.RequestError as req_err:
                    print(
                        f"Attempt {attempt + 1} - Request error occurred: {str(req_err)} with search engine {search_engine}"
                    )
                except json.JSONDecodeError as json_err:
                    print(
                        f"Attempt {attempt + 1} - JSON decode error occurred: {str(json_err)} with search engine {search_engine}"
                    )
                except Exception as e:
                    print(
                        f"Attempt {attempt + 1} - Exception: {e} with search engine {search_engine}"
                    )

                if attempt < retries - 1:
                    asyncio.sleep(delay)
                else:
                    break

    print("Failed to retrieve response after retries.")
    return None


async def get_data(_id, connector):

    fetched_profile_data = await postgres_fetch_profile_data(
        connector, [_id], tables=["companies", "experience", "location"]
    )

    id = _id
    title = ""
    headline = ""
    description = ""
    universal_name = ""
    company_name = ""
    first_location = ""
    country = ""

    if fetched_profile_data and isinstance(fetched_profile_data, dict):
        profile_data = fetched_profile_data.get(str(_id), {})

        profile = profile_data.get("profile", {})
        experience = profile_data.get("experience", [])
        companies = profile_data.get("companies", [])
        location = profile_data.get("location", [])

        if profile:
            headline = profile.get("headline", "")

        if isinstance(experience, list) and experience:
            first_experience = next(
                (exp for exp in experience if exp.get("index") == 0), experience[0]
            )
            title = first_experience.get("title", "")
            description = first_experience.get("description", "")
            company_id = first_experience.get("company_id", "")

            if isinstance(companies, list) and companies:
                first_company = next(
                    (comp for comp in companies if comp.get("id") == company_id), None
                )
                if first_company:
                    universal_name = first_company.get("universal_name", "")
                    company_name = first_company.get("name", "")

        if isinstance(location, list) and location:
            first_location = location[0].get("location", "")
            country = location[0].get("country", "")
        elif isinstance(location, dict):
            first_location = location.get("location", "")
            country = location.get("country", "")

    else:
        print("No valid profile data found.")

    target_data = {
        "id": id,
        "title": title,
        "headline": headline,
        "description": description,
        "country": country,
        "location": first_location,
    }

    return universal_name, company_name, json.dumps(target_data, indent=4)


async def get_company_data(li_universalname, client):
    query = {
        "_source": [
            "cb_full_description",
            "li_industries",
            "li_description",
            "li_specialties",
            "li_size",
        ],
        "query": {"match": {"li_universalname": li_universalname}},
    }

    response = await client.search(index="company", body=query)

    hits = response.get("hits", {}).get("hits", [])
    if hits:
        return hits[0]["_source"]
    else:
        return None


def post_process_gpt_output(response):
    return (
        response[response[: response.rfind("<")].rfind("<") :]
        .split("<")[1]
        .split(">")[1]
        .strip()
    )


def parse_to_dict(input_string, product_flag):
    if product_flag:
        company_product_dict = {}
        pattern = r"\d+\.\s*(\w+.*?)~\[(.*?)\]"
        matches = re.findall(pattern, input_string)
        for match in matches:
            company_name = match[0].strip()
            product_names = [item.strip().strip('"') for item in match[1].split(",")]
            company_product_dict[company_name] = product_names
        return company_product_dict
    else:
        pattern = r'"(.*?)":\s*(\d+)'
        matches = re.findall(pattern, input_string)
        empty_list_dict = {
            company: [] for company, number_str in matches if int(number_str) > 6
        }

        return empty_list_dict


async def get_base_product(title, description, headline, company):
    messages = [
        {
            "role": "system",
            "content": GET_BASE_PRODUCT_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": GET_BASE_PRODUCT_USER_PROMPT
            + f"""
                <Input>
                    title: "{title}"
                    description: "{description}"
                    headline: "{headline}"
                    company: "{company}"
                </Input>
            """,
        },
    ]
    response = await invoke(
        messages=messages,
        temperature=0,
        model="openai/gpt-4.1",
        fallbacks=["anthropic/claude-sonnet-4-latest"],
    )

    response = post_process_gpt_output(response)

    return response


async def function_keywords(title, headline, description):
    system_message = {
        "role": "system",
        "content": FUNCTION_KEYWORDS_SYSTEM_PROMPT,
    }

    user_message = {
        "role": "user",
        "content": FUNCTION_KEYWORDS_USER_PROMPT,
    }

    user_message["content"] += f"Title: {title}\n"

    user_message["content"] += f"Headline: {headline}\n"

    retries = 5
    for attempt in range(retries):
        try:
            response = await invoke(
                messages=[system_message, user_message],
                temperature=0,
                model="openai/gpt-4.1",
                fallbacks=["anthropic/claude-sonnet-4-latest"],
            )

            text = response[response.find("{") : response.rfind("}") + 1]
            try:
                response = json.loads(text)
            except json.JSONDecodeError:
                response = ast.literal_eval(text)
            return response

        except Exception as e:
            if attempt == retries - 1:
                raise
            await asyncio.sleep(1)


async def get_similar_companies(
    company_name, company_data, company_size, product_or_service
):
    system_message = {
        "role": "system",
        "content": GET_SIMILAR_COMPANIES_SYSTEM_PROMPT,
    }

    product_flag = False

    if "NO_PRODUCTS" not in product_or_service:
        product_flag = True
        user_message = {
            "role": "user",
            "content": GET_SIMILAR_COMPANIES_WITH_KEYWORDS_USER_PROMPT
            + f"""
                Here is the product name: "{product_or_service}", the company name is "{company_name}
            """,
        }
    else:
        user_message = {
            "role": "user",
            "content": GET_SIMILAR_COMPANIES_WITHOUT_KEYWORDS_USER_PROMPT
            + f"""
            The company name is: {company_name}
            """,
        }

    if company_size < 5000:
        user_message[
            "content"
        ] += f"""
        Here is the company's data for more context:{company_data} and the company size is: {company_size}
        **VERY IMPORTANT INSTRUCTION**: Make sure to generate companies with comparable company size! If a company as size between 1-500 generate micro sized companies if it's between 501 and 1000 generate small sized companies if it's above 1001-5000 then generate mid sized companies. DO NOT GENERATE VERY LARGE OR HUGE COMPANIES AT ALL. IF YOU FAIL AT THIS YOU'VE FAILED AT YOUR TASK AND YOU ARE A FAILURE.
        Try to generate as many accurate companies as you can."""

    retries = 5
    for attempt in range(retries):
        try:
            response = await invoke(
                messages=[system_message, user_message],
                temperature=0,
                model="openai/gpt-4.1",
                fallbacks=["anthropic/claude-sonnet-4-latest"],
            )

            response = post_process_gpt_output(response)

            if product_flag:
                parsed_data = parse_to_dict(response, product_flag)
                return parsed_data
            else:
                parsed_data = parse_to_dict(response, product_flag)
                return parsed_data

        except Exception as e:
            print(e)
            if attempt == retries - 1:
                raise
            await asyncio.sleep(1)


async def normalize_title(title):
    system_message = {
        "role": "system",
        "content": NORMALIZE_TITLE_SYSTEM_PROMPT,
    }

    user_message = {
        "role": "user",
        "content": NORMALIZE_TITLE_USER_PROMPT
        + f"""
                Given Title: "{title}" 
        """,
    }

    retries = 5
    for attempt in range(retries):
        try:
            response = await invoke(
                messages=[system_message, user_message],
                temperature=0,
                model="openai/gpt-4.1",
                fallbacks=["anthropic/claude-sonnet-4-latest"],
            )

            response = post_process_gpt_output(response)

            titles_list = eval(response)
            return titles_list

        except Exception as e:
            if attempt == retries - 1:
                raise
            await asyncio.sleep(1)


async def similar_regions(country, company):
    user_message = {
        "role": "user",
        "content": SIMILAR_REIGOINS_USER_PROMPT
        + f""" The company is: {company}, and the country is: {country}""",
    }
    system_message = {
        "role": "system",
        "content": SIMILAR_REIGOINS_SYSTEM_PROMPT,
    }

    try:
        response = await invoke(
            messages=[system_message, user_message],
            model="openai/gpt-4o-mini",
            temperature=0,
            fallbacks=["anthropic/claude-3-5-haiku-latest"],
        )

        response = post_process_gpt_output(response)

        return list(eval(response))
    except:
        return 0


async def validator_agent(title):
    user_message = {
        "role": "user",
        "content": VALIDATOR_AGENT_USER_PROMPT + f""" The title is: {title}""",
    }
    system_message = {
        "role": "system",
        "content": VALIDATOR_AGENT_SYSTEM_PROMPT,
    }

    try:
        response = await invoke(
            messages=[system_message, user_message],
            model="openai/gpt-4o-mini",
            temperature=0,
            fallbacks=["anthropic/claude-3-5-haiku-latest"],
        )

        return int(post_process_gpt_output(response))
    except:
        return 0


async def company_competitors(
    profile_data, company_name, company_data, universal_name, product_or_service, client
):

    company_size = await get_company_size(universal_name, client)
    size = int(company_size.get("li_size", ""))

    companies = await get_similar_companies(
        company_name, company_data, size, product_or_service
    )

    competitor_companies = list(companies.keys())

    competitor_universal_names = await asyncio.gather(
        *[get_linkedin_identifier(company) for company in competitor_companies]
    )

    competitor_universal_names = {
        company: universal_name
        for company, universal_name in zip(
            competitor_companies, competitor_universal_names
        )
    }

    external_competitors = {
        competitor_universal_names[name]: companies[name]
        for name in competitor_companies
    }

    external_competitors = {
        k: v for k, v in external_competitors.items() if k is not None
    }

    competitors_dict = {**external_competitors}

    return competitors_dict
