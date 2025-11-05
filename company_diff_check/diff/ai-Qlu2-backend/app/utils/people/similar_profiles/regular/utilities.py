import os
import re
import math
import json
import asyncio
import traceback

from app.utils.people.similar_profiles.regular.prompts import (
    GET_SIMILAR_COMPANIES_SYSTEM_PROMPT,
    GET_SIMILAR_COMPANIES_WITH_KEYWORDS_USER_PROMPT,
    GET_SIMILAR_COMPANIES_WITHOUT_KEYWORDS_USER_PROMPT,
    BUSINESS_FUNCTION_USER_PROMPT,
    EXECUTIVE_OR_NOT_USER,
    ONE_LINE_KEYWORD_SYSTEM,
    EXECUTIVE_OR_NOT_SYSTEM,
    RELATIVE_EXPERIENCE_SYSTEM_PROMPT,
    RELATIVE_EXPERIENCE_USER_PROMPT,
    RELATIVE_EXPERIENCE_GROUP_RANK_SYSTEM_PROMPT,
    RELATIVE_EXPERIENCE_GROUP_RANK_USER_PROMPT,
    GET_BASE_PRODUCT_SYSTEM_PROMPT,
    GET_BASE_PRODUCT_USER_PROMPT,
    TITLES_USER_PROMPT,
    FUNCTION_KEYWORDS_USER_PROMPT,
    SIMILAR_TITLES_USER_PROMPT,
    LOWER_TITLES_USER_PROMPT,
    INDUSTRY_FOR_CACHE_PROMPT,
)
from app.utils.people.similar_profiles.regular.p2p import company_recommender
from app.utils.people.similar_profiles.regular.linkedin_identifier import (
    get_linkedin_identifier,
)

from qutils.llm.asynchronous import invoke, stream
from qutils.database.post_gres import postgres_fetch_profile_data

from app.utils.search.aisearch.company.generation.utilities import cache_industry


def post_process_gpt_output(response):
    return (
        response[response[: response.rfind("<")].rfind("<") :]
        .split("<")[1]
        .split(">")[1]
        .strip()
    )


def filter_invalid_companies(companies):
    """
    Filters out companies that contain an apostrophe (single quote).
    """
    if isinstance(companies, dict):
        return {key: value for key, value in companies.items() if "'" not in key}
    elif isinstance(companies, list):
        return [
            company
            for company in companies
            if isinstance(company, str) and "'" not in company
        ]
    return companies


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
            company: [] for company, number_str in matches if int(number_str) >= 6
        }

        return empty_list_dict


def transform_company_sizes(companies_data):
    transformed = {}

    for company, metrics in companies_data.items():
        if not metrics:
            transformed[company] = 0
            continue

        li_size = metrics.get("li_size")
        li_staffcount = metrics.get("li_staffcount")
        li_staffcountrange = metrics.get("li_staffcountrange") or {}

        if li_size is not None or li_staffcount is not None:
            max_val = max(
                li_size if li_size else 0, li_staffcount if li_staffcount else 0
            )
        else:
            max_val = li_staffcountrange.get("end", 0)
            if max_val is None:
                max_val = 0

        transformed[company] = int(math.floor(max_val))

    return transformed


async def get_company_sizes(universal_names, client):
    query = {
        "size": 1000,
        "_source": [
            "li_universalname",
            "li_size",
            "li_staffcount",
            "li_staffcountrange",
        ],
        "query": {"terms": {"li_universalname": universal_names}},
    }

    response = await client.search(index=os.getenv("ES_COMPANIES_INDEX"), body=query)

    hits = response.get("hits", {}).get("hits", [])

    results = {}
    for hit in hits:
        source = hit.get("_source", {})
        universal_name = source.get("li_universalname")
        if universal_name:
            results[universal_name] = {
                "li_size": source.get("li_size"),
                "li_staffcount": source.get("li_staffcount"),
                "li_staffcountrange": source.get("li_staffcountrange"),
            }

    return transform_company_sizes(results)


async def get_company_universalname_by_urn(urn, client):
    query = {"query": {"term": {"li_urn": {"value": urn}}}}

    response = await client.search(index=os.getenv("ES_COMPANIES_INDEX"), body=query)

    hits = response.get("hits", {}).get("hits", [])

    for hit in hits:
        source = hit.get("_source", {})
        if source.get("li_urn") == urn:
            return source.get("li_universalname")

    return None


async def get_company_size(li_universalname, client):
    query = {
        "_source": ["li_size", "li_industries", "li_specialties"],
        "query": {"match": {"li_universalname": li_universalname}},
    }

    response = await client.search(index=os.getenv("ES_COMPANIES_INDEX"), body=query)

    hits = response.get("hits", {}).get("hits", [])
    if hits:
        source = hits[0]["_source"]
        return (
            source.get("li_size"),
            source.get("li_industries"),
            source.get("li_specialties"),
        )
    else:
        return None, None, None


async def get_all_experiences(esid, client):
    query = {
        "_source": ["experience.title", "experience.end"],
        "query": {
            "bool": {
                "must": [
                    {"term": {"_id": esid}},
                    {
                        "nested": {
                            "path": "experience",
                            "query": {"exists": {"field": "experience.end"}},
                        }
                    },
                ]
            }
        },
    }

    response = await client.search(index=os.getenv("ES_PROFILES_INDEX"), body=query)

    hits = response.get("hits", {}).get("hits", [])
    titles = []

    if hits:
        experiences = hits[0]["_source"].get("experience", [])
        titles = [exp["title"] for exp in experiences if exp.get("end") is not None]

    return titles


async def get_all_active_experiences(_id, client):
    query = {
        "_source": [
            "experience.index",
            "experience.title",
            "experience.company",
            "experience.end",
        ],
        "query": {
            "bool": {
                "must": [{"term": {"_id": _id}}],
                "filter": {
                    "nested": {
                        "path": "experience",
                        "query": {
                            "bool": {
                                "must_not": [{"exists": {"field": "experience.end"}}]
                            }
                        },
                        "inner_hits": {
                            "_source": [
                                "experience.index",
                                "experience.title",
                                "experience.company",
                            ]
                        },
                    }
                },
            }
        },
    }

    response = await client.search(index=os.getenv("ES_PROFILES_INDEX"), body=query)

    hits = response.get("hits", {}).get("hits", [])
    if hits:
        inner_hits = (
            hits[0]
            .get("inner_hits", {})
            .get("experience", {})
            .get("hits", {})
            .get("hits", [])
        )
        return [
            {
                "index": item["_source"]["index"],
                "title": item["_source"]["title"],
                "company": item["_source"]["company"],
            }
            for item in inner_hits
        ]
    else:
        return []


async def get_data(_id, expereience_index, connector):
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
            summary = profile.get("summary", "")

        if isinstance(experience, list) and experience:
            first_experience = next(
                (exp for exp in experience if exp.get("index") == expereience_index),
                experience[0],
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
                    company_urn = first_company.get("urn", "")

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
        "summary": summary,
        "description": description,
        "country": country,
        "location": first_location,
    }

    return (
        universal_name,
        company_name,
        f"urn:li:fsd_company:{company_urn}",
        json.dumps(target_data, indent=4),
    )


async def get_company_location(universal_name, client):
    query = {
        "_source": ["li_headquarter.country"],
        "query": {"term": {"li_universalname": universal_name}},
    }

    response = await client.search(index="company", body=query)

    hits = response.get("hits", {}).get("hits", [])
    result = {"location": "", "metro_area": "", "country": ""}

    if hits:
        source = hits[0].get("_source", {})
        exact_country = source.get("li_headquarter", {}).get("country", "")
        result["country"] = exact_country

    return result


async def process_location(location):
    if location:
        parts = location.split(",")

        if len(parts) > 2:
            processed_location = ",".join(parts[:-1]).strip()
        elif len(parts) == 2:
            processed_location = parts[0].strip()
        else:
            processed_location = location.strip()
        return processed_location
    else:
        return None


async def process_country(country):
    if country:
        if "," in country:
            return country.rsplit(",", 1)[-1].strip()
        else:
            return country.strip()
    else:
        return None


async def get_location_data(profile_id, client):

    query = {
        "_source": ["location", "metro_area", "country"],
        "query": {"match": {"_id": profile_id}},
    }

    index = os.environ.get("ES_PROFILES_INDEX", "profiles")
    response = await client.search(index=index, body=query)

    hits = response.get("hits", {}).get("hits", [])
    if hits:
        source = hits[0].get("_source", {})
        location = source.get("location", "")
        metro_area = source.get("metro_area", "")
        country = source.get("country", "")

        processed_location, processed_country = await asyncio.gather(
            process_location(location), process_country(country)
        )

        return {
            "location": processed_location,
            "metro_area": metro_area,
            "country": processed_country,
        }

    return {"location": "", "metro_area": "", "country": ""}


async def astronomer(title):
    user_prompt = (
        EXECUTIVE_OR_NOT_USER
        + f"""
        <Title>
            {title}
        </Title>

    """
    )
    messages = [
        {"role": "system", "content": EXECUTIVE_OR_NOT_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]

    response = await invoke(
        messages=messages,
        temperature=0,
        model="openai/gpt-4o-mini",
        fallbacks=["anthropic/claude-3-5-haiku-latest"],
    )

    response = eval(response)["classification"]
    return response


async def drill_relative_experience(data):
    system_message = {
        "role": "system",
        "content": RELATIVE_EXPERIENCE_SYSTEM_PROMPT,
    }

    user_message = {
        "role": "user",
        "content": RELATIVE_EXPERIENCE_USER_PROMPT
        + f"""
                Give Data: "{data}" 
        """,
    }

    messages = [system_message, user_message]

    retries = 5
    for attempt in range(retries):
        try:
            response = await invoke(
                messages=messages,
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


async def drill_relative_experience_fagr(experiences, filters):
    system_message = {
        "role": "system",
        "content": RELATIVE_EXPERIENCE_GROUP_RANK_SYSTEM_PROMPT,
    }

    user_message = {
        "role": "user",
        "content": RELATIVE_EXPERIENCE_GROUP_RANK_USER_PROMPT
        + f"""
                Given all active experiecnes: {experiences}
                To drill relevant experience use these fileters: "{filters}" 
        """,
    }

    messages = [system_message, user_message]

    retries = 5
    for attempt in range(retries):
        try:
            response = await invoke(
                messages=messages,
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

    response = await client.search(index=os.getenv("ES_COMPANIES_INDEX"), body=query)

    hits = response.get("hits", {}).get("hits", [])
    if hits:
        return hits[0]["_source"]
    else:
        return None


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
    user_message = {
        "role": "user",
        "content": FUNCTION_KEYWORDS_USER_PROMPT,
    }

    user_message["content"] += f"Title: {title}\n"
    user_message["content"] += f"Headline: {headline}\n"
    user_message["content"] += f"Title: {description}\n"

    response = await invoke(
        model="anthropic/claude-sonnet-4-latest",
        messages=[user_message],
        temperature=0,
        fallbacks=["openai/gpt-4.1"],
    )

    response = post_process_gpt_output(response)
    response = eval(response)

    return response


async def get_similar_companies(
    profile_string,
    company_name,
    company_data,
    company_size,
    product_or_service,
    industry,
    ground_truth,
    client,
    hashmap_companies=None,
):
    if company_size <= 100:
        system_message = {
            "role": "system",
            "content": GET_SIMILAR_COMPANIES_SYSTEM_PROMPT,
        }
        product_flag = False
        if "NO_PRODUCTS" not in product_or_service:
            product_flag = True
            user_message = {
                "role": "user",
                "content": (
                    GET_SIMILAR_COMPANIES_WITH_KEYWORDS_USER_PROMPT
                    + f"""
                    Here is the product name: "{product_or_service}", 
                    the company name is "{company_name}, 
                    the industry and sub_industry are {ground_truth}
                    """
                ),
            }
        else:
            user_message = {
                "role": "user",
                "content": (
                    GET_SIMILAR_COMPANIES_WITHOUT_KEYWORDS_USER_PROMPT
                    + f"""
                    The company name is: {company_name} ,
                    the industry and sub_industry are {ground_truth}
                    """
                ),
            }
        if company_size < 5000:
            user_message[
                "content"
            ] += f"""
            Here is the company's data for more context: {company_data} 
            and the company size is: {company_size}, 
            the industry and sub_industry are {ground_truth}

            **VERY IMPORTANT INSTRUCTION**: 
            Make sure to generate companies with comparable company size! 
            If a company has size between 1-500 generate micro-sized companies, 
            if it's between 501 and 1000 generate small-sized companies, 
            if it's between 1001-5000 then generate mid-sized companies. 
            DO NOT GENERATE VERY LARGE OR HUGE COMPANIES AT ALL. 
            IF YOU FAIL AT THIS YOU'VE FAILED AT YOUR TASK AND YOU ARE A FAILURE.

            Try to generate as many accurate companies as you can.
            """

        tasks = []
        try:
            output = ""
            hashmap = ""
            company = ""
            companies_ = []
            services_ = []
            messages = [system_message, user_message]

            async for chunk in stream(
                messages=messages, model="openai/gpt-4.1", temperature=0
            ):
                if product_flag:
                    if (
                        "<predict>" in output.lower()
                        and "</predict>" not in output.lower()
                    ):
                        hashmap += chunk
                        if '"]' in chunk:
                            pattern = r"^\s*\d+\.\s*(.*?)~\[(.*)\]$"
                            match = re.search(pattern, hashmap)
                            if match:
                                company = match.group(1).strip()
                                services = match.group(2).split('", "')
                                services = [s.strip('"') for s in services]

                                tasks.append(
                                    asyncio.create_task(
                                        company_recommender(
                                            company,
                                            ground_truth,
                                            client,
                                            profile_string,
                                        )
                                    )
                                )
                                companies_.append(company)
                                services_.append(services)
                            hashmap = ""
                else:
                    if (
                        "<output>" in output.lower()
                        and "</output>" not in output.lower()
                    ):
                        hashmap += chunk
                        if '"' in hashmap:
                            company += chunk
                        if "," in hashmap:
                            pattern = r'"([^"]+)":\s*(\d+)'
                            match = re.search(pattern, company)
                            if match:
                                company = match.group(1)
                                score = int(match.group(2))
                                if score >= 8:
                                    tasks.append(
                                        asyncio.create_task(
                                            company_recommender(
                                                company,
                                                ground_truth,
                                                client,
                                                profile_string,
                                            )
                                        )
                                    )
                                else:
                                    tasks.append(
                                        asyncio.create_task(
                                            asyncio.wait_for(
                                                get_linkedin_identifier(
                                                    company,
                                                    industry,
                                                    client,
                                                    hashmap_companies,
                                                ),
                                                timeout=5.0,
                                            )
                                        )
                                    )
                            company = ""
                            hashmap = ""

                output += chunk

            if companies_:
                p2p = []
                llm = []
                while tasks:
                    if len(tasks) == 0:
                        break

                    task = tasks.pop(0)
                    if not task.done():
                        await asyncio.sleep(0.1)
                        if not task.done():
                            tasks.append(task)
                            continue

                    try:
                        response = task.result()
                    except asyncio.TimeoutError:
                        print("Task timed out while calling get_linkedin_identifier.")
                        response = None
                    except asyncio.CancelledError:
                        print(
                            "Task was cancelled while calling get_linkedin_identifier."
                        )
                        response = None

                    if isinstance(response, list):
                        p2p.extend(response)
                    else:
                        llm.append(response)

                d_companies_llm = {}
                d_companies_p2p = {}
                for index, universal_name in enumerate(p2p):
                    try:
                        if universal_name:
                            d_companies_p2p[universal_name] = services_[index]
                    except:
                        if universal_name:
                            d_companies_p2p[universal_name] = []
                return d_companies_llm, d_companies_p2p

            else:
                p2p = []
                llm = []
                while tasks:
                    if len(tasks) == 0:
                        break

                    task = tasks.pop(0)
                    if not task.done():
                        await asyncio.sleep(0.1)
                        if not task.done():
                            tasks.append(task)
                            continue

                    try:
                        response = task.result()
                    except asyncio.TimeoutError:
                        print("Task timed out while calling get_linkedin_identifier.")
                        response = None
                    except asyncio.CancelledError:
                        print(
                            "Task was cancelled while calling get_linkedin_identifier."
                        )
                        response = None

                    if isinstance(response, list):
                        p2p.extend(response)
                    else:
                        llm.append(response)

                p2p = list(set(p2p))
                filtered_p2p = [value for value in p2p if value not in llm]

                d_companies_p2p = {c: [] for c in filtered_p2p if c}
                d_companies_llm = {c: [] for c in llm if c}
                return d_companies_llm, d_companies_p2p

        except Exception as e:
            print(e)
            traceback.print_exc()
            return {}, {}

    else:
        system_message = {
            "role": "system",
            "content": GET_SIMILAR_COMPANIES_SYSTEM_PROMPT,
        }
        product_flag = False
        if "NO_PRODUCTS" not in product_or_service:
            product_flag = True
            user_message = {
                "role": "user",
                "content": (
                    GET_SIMILAR_COMPANIES_WITH_KEYWORDS_USER_PROMPT
                    + f"""
                    Here is the product name: "{product_or_service}", 
                    the company name is "{company_name}, 
                    the industry and sub_industry are {ground_truth}
                    """
                ),
            }
        else:
            user_message = {
                "role": "user",
                "content": (
                    GET_SIMILAR_COMPANIES_WITHOUT_KEYWORDS_USER_PROMPT
                    + f"""
                    The company name is: {company_name} ,
                    the industry and sub_industry are {ground_truth}
                    """
                ),
            }
        if company_size < 5000:
            user_message[
                "content"
            ] += f"""
            Here is the company's data for more context: {company_data} 
            and the company size is: {company_size}, 
            the industry and sub_industry are {ground_truth}

            **VERY IMPORTANT INSTRUCTION**: 
            Make sure to generate companies with comparable company size! 
            If a company has size between 1-500 generate micro-sized companies, 
            if it's between 501 and 1000 generate small-sized companies, 
            if it's between 1001-5000 then generate mid-sized companies. 
            DO NOT GENERATE VERY LARGE OR HUGE COMPANIES AT ALL. 
            IF YOU FAIL AT THIS YOU'VE FAILED AT YOUR TASK AND YOU ARE A FAILURE.

            Try to generate as many accurate companies as you can.
            """

        tasks = []
        try:
            output = ""
            hashmap = ""
            company = ""
            companies_ = []
            services_ = []
            messages = [system_message, user_message]

            async for chunk in stream(
                messages=messages,
                model="openai/gpt-4.1",
                temperature=0,
            ):
                if product_flag:
                    if (
                        "<predict>" in output.lower()
                        and "</predict>" not in output.lower()
                    ):
                        hashmap += chunk
                        if '"]' in chunk:
                            pattern = r"^\s*\d+\.\s*(.*?)~\[(.*)\]$"
                            match = re.search(pattern, hashmap)
                            if match:
                                company = match.group(1).strip()
                                services = match.group(2).split('", "')
                                services = [s.strip('"') for s in services]

                                tasks.append(
                                    asyncio.create_task(
                                        asyncio.wait_for(
                                            get_linkedin_identifier(
                                                company,
                                                industry,
                                                client,
                                                hashmap_companies,
                                            ),
                                            timeout=5.0,
                                        )
                                    )
                                )
                                companies_.append(company)
                                services_.append(services)
                            hashmap = ""
                else:
                    if (
                        "<output>" in output.lower()
                        and "</output>" not in output.lower()
                    ):
                        hashmap += chunk
                        if '"' in hashmap:
                            company += chunk
                        if "," in hashmap:
                            pattern = r'"([^"]+)":\s*(\d+)'
                            match = re.search(pattern, company)
                            if match:
                                company = match.group(1)
                                score = int(match.group(2))
                                if score >= 6:
                                    tasks.append(
                                        asyncio.create_task(
                                            asyncio.wait_for(
                                                get_linkedin_identifier(
                                                    company,
                                                    industry,
                                                    client,
                                                    hashmap_companies,
                                                ),
                                                timeout=5.0,
                                            )
                                        )
                                    )
                                else:
                                    pass
                            company = ""
                            hashmap = ""

                output += chunk

            if companies_:
                llm = []
                while tasks:
                    if len(tasks) == 0:
                        break

                    task = tasks.pop(0)
                    if not task.done():
                        await asyncio.sleep(0.1)
                        if not task.done():
                            tasks.append(task)
                            continue

                    try:
                        response = task.result()
                    except asyncio.TimeoutError:
                        print("Task timed out while calling get_linkedin_identifier.")
                        response = None
                    except asyncio.CancelledError:
                        print(
                            "Task was cancelled while calling get_linkedin_identifier."
                        )
                        response = None

                    llm.append(response)

                d_companies_llm = {}
                for index, universal_name in enumerate(llm):
                    try:
                        if universal_name:
                            d_companies_llm[universal_name] = services_[index]
                    except IndexError:
                        if universal_name:
                            d_companies_llm[universal_name] = []

                return d_companies_llm, {}

            else:
                p2p = []
                llm = []

                while tasks:
                    if len(tasks) == 0:
                        break

                    task = tasks.pop(0)
                    if not task.done():
                        await asyncio.sleep(0.1)
                        if not task.done():
                            tasks.append(task)
                            continue

                    try:
                        response = task.result()
                    except asyncio.TimeoutError:
                        print("Task timed out while calling get_linkedin_identifier.")
                        response = None
                    except asyncio.CancelledError:
                        print(
                            "Task was cancelled while calling get_linkedin_identifier."
                        )
                        response = None

                    if isinstance(response, list):
                        p2p.extend(response)
                    else:
                        llm.append(response)

                p2p = list(set(p2p))
                filtered_p2p = [value for value in p2p if value not in llm]

                d_companies_llm = {c: [] for c in llm if c}
                return d_companies_llm, {}

        except Exception as e:
            print(e)
            traceback.print_exc()
            return {}, {}


async def business_function(title, description, headline, about):
    user_prompt = f"""
        <Person_Information>
            Current Role: {title},
            Description: {description},
            Headline: {headline},
            About: {about}
        </Person_Information>

    """
    messages = [
        {"role": "system", "content": BUSINESS_FUNCTION_USER_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    response = await invoke(
        model="anthropic/claude-sonnet-4-latest",
        messages=messages,
        temperature=0,
        fallbacks=["openai/gpt-4.1"],
    )

    response = (
        response.replace("null", "None")
        .replace("true", "True")
        .replace("false", "False")
    )
    response = (
        response[response.rfind("<Output>") : response.rfind("</Output>")]
        .replace("<Output>", "")
        .replace("<", "")
    )
    response = response[response.find("{") : response.rfind("}") + 1]
    response = eval(response.strip())
    return response


async def similar_titles(title, functions):
    user_prompt = (
        SIMILAR_TITLES_USER_PROMPT
        + f"""
        <Person_Information>
            Headline: {title},
            Business Function: {functions}

        </Person_Information>

    """
    )
    messages = [
        {"role": "user", "content": user_prompt},
    ]

    response = await invoke(
        model="anthropic/claude-sonnet-4-latest",
        messages=messages,
        temperature=0,
        fallbacks=["openai/gpt-4.1"],
    )

    response = (
        response.replace("null", "None")
        .replace("true", "True")
        .replace("false", "False")
    )
    response = (
        response[response.rfind("<Output>") : response.rfind("</Output>")]
        .replace("<Output>", "")
        .replace("<", "")
    )
    response = response[response.find("{") : response.rfind("}") + 1]
    response = eval(response.strip())
    return response


async def Executive_Classification(title, functions):
    user_prompt = (
        TITLES_USER_PROMPT
        + f"""
        <Person_Information>
            Headline: {title},
            Business Function: {functions}
        </Person_Information>

    """
    )
    messages = [
        {"role": "user", "content": user_prompt},
    ]

    response = await invoke(
        model="anthropic/claude-sonnet-4-latest",
        messages=messages,
        temperature=0,
        fallbacks=["openai/gpt-4.1"],
    )

    response = (
        response.replace("null", "None")
        .replace("true", "True")
        .replace("false", "False")
    )
    response = (
        response[response.rfind("<Output>") : response.rfind("</Output>")]
        .replace("<Output>", "")
        .replace("<", "")
    )
    response = response[response.find("{") : response.rfind("}") + 1]
    response = eval(response.strip())
    return response


async def Executive_Classification_Internal(title, functions):
    user_prompt = (
        LOWER_TITLES_USER_PROMPT
        + f"""
        <Person_Information>
            Headline: {title},
        </Person_Information>

    """
    )
    messages = [
        {"role": "user", "content": user_prompt},
    ]

    response = await invoke(
        model="anthropic/claude-sonnet-4-latest",
        messages=messages,
        temperature=0,
        fallbacks=["openai/gpt-4.1"],
    )

    response = (
        response.replace("null", "None")
        .replace("true", "True")
        .replace("false", "False")
    )
    response = (
        response[response.rfind("<Output>") : response.rfind("</Output>")]
        .replace("<Output>", "")
        .replace("<", "")
    )
    response = response[response.find("{") : response.rfind("}") + 1]
    response = eval(response.strip())

    return response


async def normalize_title(info, description, headline, about, service_flag):

    if service_flag == "external":
        execs_functions = await business_function(info, description, headline, about)
        keywords_from_dict = execs_functions.get("keywords", [])

        flag = None
        if execs_functions.get("executive", None):
            all_info = await Executive_Classification(
                info, execs_functions.get("business_functions")
            )
        else:
            flag = "non-executive"
            all_titles = await similar_titles(info, execs_functions)
            return {
                "flag": flag,
                "title_dict": all_titles,
                "skills": keywords_from_dict if keywords_from_dict else [],
                "ranks": [],
            }
        final = {}
        csuite = all_info.get("CSuite", {})
        executives = {
            key: value
            for key, value in all_info.get("Executive", {}).items()
            if value >= 7
        }
        board = all_info.get("Board", [])

        csuite_values = list(csuite.keys()) if csuite else []
        executives_values = list(executives.keys()) if executives else []
        jsut_ranks = csuite_values + executives_values + board

        if csuite.get("CEO", None) or "Chair" in board:
            flag = "CEO/Chairman"
        else:
            flag = "executive"

        for key, value in csuite.items():
            final[key.lower()] = (value / 10) * 5.8

        if executives and execs_functions.get("business_functions"):
            for key, value in executives.items():
                for function, function_value in execs_functions.get(
                    "business_functions"
                ).items():
                    final[f"{key} {function}".lower()] = (
                        (value + function_value) / 20
                    ) * 5.8
        elif executives:
            for key, value in executives.items():
                final[f"{key}".lower()] = (value / 10) * 5.8

        if "Chair" in board:
            if not final:
                final["chair"] = 6
            else:
                final["chair"] = 5.5

        if "Board Member" in board:
            final["board member"] = 4

        if keywords_from_dict:
            skills = keywords_from_dict
        else:
            skills = []

        return {
            "flag": flag,
            "title_dict": final,
            "skills": skills,
            "ranks": jsut_ranks,
        }

    elif service_flag == "internal":
        execs_functions = await business_function(info, description, headline, about)
        keywords_from_dict = execs_functions.get("keywords", [])

        flag = None

        if execs_functions.get("executive", None):
            all_info = await Executive_Classification_Internal(
                info, execs_functions.get("business_functions")
            )
        else:
            flag = "non-executive"
            all_titles = await similar_titles(info, execs_functions)

            return {
                "flag": flag,
                "title_dict": all_titles,
                "skills": keywords_from_dict if keywords_from_dict else [],
                "ranks": [],
            }

        final = {}
        current_titles = all_info.get("current_titles", {})
        executives = {
            key: value
            for key, value in all_info.get("Executive", {}).items()
            if value >= 7
        }
        board_flag = all_info.get("Board", False)
        current_titles_lower = [title.lower() for title in current_titles]
        jsut_ranks = []

        if "ceo" in current_titles_lower:
            final["ceo"] = 6
            final["chief executive officer"] = 6
            flag = "CEO/Chairman"
            jsut_ranks = ["CEO", "Chief Executive Officer"]
        elif "president" in current_titles_lower:
            final["president"] = 6
            jsut_ranks = ["President"]
            flag = "CEO/Chairman"
        elif "partner" in current_titles_lower:
            final["partner"] = 6
            jsut_ranks = ["partner"]
            flag = "CEO/Chairman"
        elif "founder" in current_titles_lower or "co-founder" in current_titles_lower:
            final["founder"] = 5
            final["co-founder"] = 5
            if "co-founder" in current_titles_lower:
                final["co-founder"] = 6
            elif "founder" in current_titles_lower:
                final["founder"] = 6
            jsut_ranks = ["Founder", "Co-Founder"]
            flag = "CEO/Chairman"
        else:
            if board_flag == True:
                final["board member"] = 4
            else:
                final = {}
            flag = "executive"

            if executives and execs_functions.get("business_functions"):
                for key, value in executives.items():
                    for function, function_value in execs_functions.get(
                        "business_functions"
                    ).items():
                        final[f"{key} {function}".lower()] = (
                            (value + function_value) / 20
                        ) * 5.8

            elif executives:
                for key, value in executives.items():
                    final[f"{key}".lower()] = (value / 10) * 5.8

        if keywords_from_dict:
            skills = keywords_from_dict
        else:
            skills = []

        return {
            "flag": flag,
            "title_dict": final,
            "skills": skills,
            "ranks": jsut_ranks,
            "current_titles": current_titles,
        }


async def fetch_industry(profile_data, company_data):
    person_title = profile_data.get("title", None)
    person_headline = profile_data.get("headline", None)
    person_description = profile_data.get("description", None)

    company_industries = company_data.get("li_industries", None)
    company_specialties = company_data.get("li_specialties", None)
    company_description = company_data.get("li_description", None)

    if not isinstance(company_specialties, list):
        company_specialties = [company_specialties]

    if not isinstance(company_industries, list):
        company_industries = [company_industries]

    company_industries = company_industries + company_specialties

    string = "The profile data is:"
    if person_title:
        string += f" Title: {person_title}"
    if person_headline:
        string += f" Headline: {person_headline}"
    if person_description:
        string += f" Description: {person_description}"
    string += " The company data is:"
    if company_industries:
        string += f" Industries: {company_industries}"

    if company_description:
        string += f" Description: {company_description}"

    claude_system = """Your name is Jared and you are an expert in identifying the industry of a person.

<Instructions>
- Given a person's data and their company determine the industries in which that person works in.
- The industry terms should be specific and should target niches, instead of being very broad
- The industry can't be more than 3 words.
- You are looking for the specific industries that the person specializes in, in the given company
- Keywords should not deviate from the main focus of the company
- After you've inferred the industries to target create multiple variations of that industry string. For example Wearables can also be Wearable, Wearable Technology etc.
- You can also give sub-industries of the industries that you have found
- Make sure to focus on the specific niche of the company, capturing all aspects of its domain
- Generate up to 15 keywords
</Instructions>
<Output Format> 
- First give at least 50 reasoning tokens or more.
- Then provide your final output enclosed within: 

<output> 
["industry 1", "industry 2", ...]
</output>
</Output Format>"""

    messages = [
        {"role": "system", "content": claude_system},
        {"role": "user", "content": string},
    ]

    results = await asyncio.gather(
        *[
            invoke(
                model="anthropic/claude-sonnet-4-latest",
                messages=messages,
                temperature=0.1,
                fallbacks=["openai/gpt-4.1"],
            ),
            get_one_line_keyword(string),
        ]
    )
    response, one_line_keyword = results
    response = post_process_gpt_output(response)
    industries = eval(response)

    return industries, one_line_keyword


async def filter_similar_companies(
    ground_truth, company_name, company_data, li_universalname, v2=False
):
    if v2:
        system_prompt = """<role> You are Jerry, an expert in finding similar profiles for recruiters </role>
<instructions>
- A good similar profiles needs to focus on company similarity and the person's role
- Given a target profile and some company information, answer the chances of finding a similar profile from the provided company
- Answer the user query by first outputting your reasoning in 3 lines then assign a score between 1-4 in <score> </score> tags
- Score of 1 means upto 25% chance, score of 2 means upto 50% chance, score of 3 means upto 75% chance and a score of 4 means upto 100% chance
</instructions>"""
        user_prompt = (
            ground_truth + f"<target_company> {company_data} </target_company>"
        )
    else:
        system_prompt = f"""<role> You are an expert in finding good candidates for a specific job role </role>
    <instructions>
    - How likely is it that {company_name} is involved in "{ground_truth}" 
    - Output your thought process in 3 lines before final score as 1, 2, 3 or 4 in <score> </score> tags
    - score of 1 means highly unlikely and the target field is irrelevant to the industry of company, score of 2 means less than 50% match, score of 3 means more than 50% match, score of 4 means perfect match
    </instructions>"""

        user_prompt = company_data

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = await invoke(
        messages=messages,
        temperature=0,
        model="openai/gpt-4.1",
        fallbacks=["anthropic/claude-sonnet-4-latest"],
    )

    matches = re.findall(r"<score>(.*?)</score>", response)

    if matches:
        return li_universalname, int(matches[0].strip())

    return li_universalname, 1


async def get_one_line_keyword(profile_data):
    system_prompt = ONE_LINE_KEYWORD_SYSTEM

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": profile_data},
    ]

    response = await invoke(
        messages=messages,
        temperature=0,
        model="openai/gpt-4.1",
        fallbacks=["anthropic/claude-sonnet-4-latest"],
    )

    return response


async def industry_for_cache(profile_data):

    user_message = {
        "role": "user",
        "content": INDUSTRY_FOR_CACHE_PROMPT,
    }

    user_message["content"] += f"Profile Data: {profile_data}\n"

    response = await invoke(
        model="anthropic/claude-sonnet-4-latest",
        messages=[user_message],
        temperature=0,
        fallbacks=["openai/gpt-4.1"],
    )

    response = post_process_gpt_output(response)
    industries_cache = eval(response)

    return industries_cache


async def companies_through_industries(
    profile_string, industries, ground_truth, client
):
    try:
        combined_clauses = []

        for term in industries:
            combined_clauses.append(
                {
                    "bool": {
                        "should": [
                            {"match_phrase": {"li_description": term}},
                            {"match": {"li_industries.keyword": term}},
                            {"match": {"li_specialties.keyword": term}},
                        ],
                        "minimum_should_match": 1,
                    }
                }
            )

        matching_threshold = math.ceil(25 * len(industries) / 100)
        if matching_threshold > 1:
            matching_threshold = matching_threshold - 1

        query = {
            "_source": [
                "li_universalname",
                "li_size",
                "li_industries",
                "li_specialties",
                "li_description",
                "li_name",
            ],
            "size": 100,
            "query": {
                "bool": {
                    "should": combined_clauses,
                    "minimum_should_match": (
                        matching_threshold if matching_threshold <= 5 else 5
                    ),
                }
            },
        }

        try:

            response = await client.search(
                index=os.getenv("ES_COMPANIES_INDEX"), body=query
            )

        except Exception as e:
            print(f"Error while querying Elasticsearch: {e}")
            return []

        other_companies = {}

        for i in response["hits"]["hits"]:
            company_string = ""
            source = i.get("_source", "")
            if source:
                li_size = source.get("li_size", 0)
                li_name = source.get("li_name", "")
                li_specialties = source.get("li_specialties", "")
                li_industry = source.get("li_industries", "")
                if not isinstance(li_specialties, list):
                    li_specialties = [li_specialties]
                li_description = source.get("li_description", "")
                if not li_size:
                    li_size = 0
                if li_size >= 3000:
                    company_string += f"<company> {li_name} </company>"
                else:
                    company_string += f"<company>\n<industries> {li_industry + li_specialties} </industry>\n<description> {li_description} </description>\n</company>"
            other_companies[source.get("li_universalname")] = {
                "string": company_string,
                "name": li_name,
            }

        if profile_string:
            filtered = await asyncio.gather(
                *[
                    filter_similar_companies(
                        profile_string,
                        other_companies[li_universalname]["name"],
                        other_companies[li_universalname]["string"],
                        li_universalname,
                        True,
                    )
                    for li_universalname in other_companies
                ]
            )
        else:
            filtered = await asyncio.gather(
                *[
                    filter_similar_companies(
                        ground_truth,
                        other_companies[li_universalname]["name"],
                        other_companies[li_universalname]["string"],
                        li_universalname,
                    )
                    for li_universalname in other_companies
                ]
            )

        filtered.sort(key=lambda x: x[1], reverse=True)

        filtered = [i[0] for i in filtered if i[1] > 2]

        return filtered
    except Exception as e:
        traceback.print_exc()
        print(f"Error while fetching companies: {e}")
        return []


async def get_experience_status(_id, experience_index, client):
    query = {
        "_source": False,
        "query": {
            "bool": {
                "must": [
                    {"term": {"_id": _id}},
                    {
                        "nested": {
                            "path": "experience",
                            "query": {"term": {"experience.index": experience_index}},
                            "inner_hits": {"_source": ["experience.end"]},
                        }
                    },
                ]
            }
        },
    }

    index = os.environ.get("ES_PROFILES_INDEX", "profile")
    response = await client.search(index=index, body=query)

    hits = response["hits"]["hits"]
    if not hits:
        return "Document not found."

    inner_hits = hits[0].get("inner_hits", {})
    experience_hits = inner_hits.get("experience", {}).get("hits", {}).get("hits", [])
    if not experience_hits:
        return "No experience found with the given index."

    experience_end = experience_hits[0]["_source"].get("end", None)
    if experience_end is not None:
        return "Past"
    else:
        return "Present"


async def company_competitors(
    profile_data, company_name, company_data, universal_name, product_or_service, client
):
    company_specialities = []
    company_data = await get_company_data(universal_name, client)

    company_specialities, ground_truth = await fetch_industry(
        profile_data, company_data
    )

    mapping_industries, hashmap_companies = await cache_industry(
        ground_truth + " companies"
    )

    profile_string = ""
    title = profile_data.get("title", "")
    headline = profile_data.get("headline", "")
    company_size = company_data.get("li_size", 0)
    if company_size:
        company_size = int(company_size)
    else:
        company_size = 0

    li_specialties = company_data.get("li_specialties", [])
    li_industries = company_data.get("li_industries", [])
    li_description = company_data.get("li_description")
    if isinstance(li_specialties, str):
        li_specialties = [li_specialties]
    if title or headline:
        profile_string += f"<target_profile_role> {title or headline} {company_name} </target_profile_role>"
        if company_size and company_size < 3000:
            li_specialties = li_specialties or []
            li_industries = li_industries or []
            li_description = li_description or ""
            company_name = company_name or ""
            profile_string += (
                f"<about_{company_name}> {company_name} operates in {li_specialties + li_industries}\n"
                f"{li_description}\n<about_{company_name}>"
            )

    company_via_industries = []
    if company_size < 5000:
        companies, company_via_industries = await asyncio.gather(
            get_similar_companies(
                profile_string,
                company_name,
                company_data,
                company_size,
                product_or_service,
                mapping_industries,
                ground_truth,
                client,
                hashmap_companies,
            ),
            companies_through_industries(
                profile_string, company_specialities, ground_truth, client
            ),
        )
    else:
        companies = await get_similar_companies(
            profile_string,
            company_name,
            company_data,
            company_size,
            product_or_service,
            mapping_industries,
            ground_truth,
            client,
            hashmap_companies,
        )

    d_companies_llm = companies[0]
    d_companies_p2p = companies[1]
    del hashmap_companies
    return d_companies_p2p, d_companies_llm, company_via_industries
