import os
from app.utils.company.competitors.prompts import (
    COMPETITOR_COMPANIES_SYSTEM_PROMPT,
    COMPETITOR_COMPANIES_UNPOPULAR_USER_PROMPT,
    COMPETITOR_COMPANIES_POPULAR_USER_PROMPT,
    COMPANY_STATUS_SYSTEM_PROMPT,
    COMPANY_STATUS_USER_PROMPT,
    GEN_LABEL_SYSTEM_PROMPT,
    GEN_LABEL_USER_PROMPT,
    COMPANY_SIZE_PREDICTION_SYSTEM_PROMPT,
    COMPANY_SIZE_PREDICTION_USER_PROMPT,
)
from qutils.llm.asynchronous import invoke


def post_process_gpt_output(response):
    return (
        response[response[: response.rfind("<")].rfind("<") :]
        .split("<")[1]
        .split(">")[1]
        .strip()
    )


async def company_fullname(company_name, client):

    query = {
        "_source": ["li_name"],
        "query": {"match": {"li_universalname": company_name}},
    }

    response = await client.search(index=os.getenv("ES_COMPANIES_INDEX"), body=query)

    hits = response["hits"]["hits"]
    if hits:
        name = hits[0]["_source"]["li_name"]
        return name
    else:
        return None


async def company_location(company_name, client):
    query = {
        "_source": ["li_headquarter"],
        "query": {"match": {"li_universalname": company_name}},
    }

    response = await client.search(index=os.getenv("ES_COMPANIES_INDEX"), body=query)

    hits = response.get("hits", {}).get("hits", [])
    if hits and isinstance(hits[0], dict):
        li_headquarter = hits[0].get("_source", {}).get("li_headquarter")
        if li_headquarter and isinstance(li_headquarter, dict):
            return li_headquarter.get("country", "United States")

    return "United States"


async def get_company_data(li_universalname, client):
    query = {
        "_source": [
            "cb_full_description",
            "li_industries",
            "li_description",
            "li_subindustry",
        ],
        "query": {"match": {"li_universalname": li_universalname}},
    }

    response = await client.search(index=os.getenv("ES_COMPANIES_INDEX"), body=query)

    hits = response.get("hits", {}).get("hits", [])
    if hits:
        return hits[0]["_source"]
    else:
        return None


async def count_search_results(uname, client):
    query = {
        "_source": ["li_staffcount", "li_size"],
        "query": {"match": {"li_universalname": uname}},
    }

    response = await client.search(index=os.getenv("ES_COMPANIES_INDEX"), body=query)

    hits = response.get("hits", {}).get("hits", [])
    if hits:
        source = hits[0]["_source"]
        return source
    else:
        return None


def filter_competitors_by_size(company_size, competitors_with_sizes):
    valid_sizes = {
        "giant_company": ["giant_company", "large_company"],
        "large_company": [
            "giant_company",
            "large_company",
            "mid_size_company",
        ],
        "mid_size_company": [
            "large_company",
            "mid_size_company",
            "small_medium_enterprise",
        ],
        "small_medium_enterprise": [
            "mid_size_company",
            "small_medium_enterprise",
            "small_company",
        ],
        "small_company": [
            "small_medium_enterprise",
            "small_company",
            "micro_enterprise",
        ],
        "micro_enterprise": [
            "small_medium_enterprise",
            "small_company",
            "micro_enterprise",
        ],
    }

    if company_size is None:
        return [competitor for competitor, _ in competitors_with_sizes]

    allowed_sizes = valid_sizes.get(company_size, [])

    filtered_competitors = [
        competitor
        for competitor, size in competitors_with_sizes
        if size is None or size in allowed_sizes
    ]

    return filtered_competitors


async def gen_label(company):
    system_message = {
        "role": "system",
        "content": GEN_LABEL_SYSTEM_PROMPT,
    }
    user_message = {
        "role": "user",
        "content": GEN_LABEL_USER_PROMPT + f"""The company is {company}.""",
    }

    response = await invoke(
        messages=[system_message, user_message],
        model="openai/gpt-4o-mini",
        temperature=0,
        fallbacks=["anthropic/claude-3-5-haiku-latest"],
    )
    response = post_process_gpt_output(response)
    return response


async def get_company_status(company):
    system_message = {
        "role": "system",
        "content": COMPANY_STATUS_SYSTEM_PROMPT,
    }

    user_message = {
        "role": "user",
        "content": COMPANY_STATUS_USER_PROMPT + f"""This is company name: {company}.""",
    }

    response = await invoke(
        messages=[system_message, user_message],
        model="openai/gpt-4o-mini",
        temperature=0,
        fallbacks=["anthropic/claude-3-5-haiku-latest"],
    )

    response = post_process_gpt_output(response)
    return response


async def get_competitor_unpopular(company, company_data, company_size, company_loc):
    user_message = {
        "role": "user",
        "content": COMPETITOR_COMPANIES_UNPOPULAR_USER_PROMPT
        + f"""
            <Input>
                This is company name: {company}. 
                This is company data: {company_data}. 
                This is company size: {company_size}.
                This is company location: {company_loc}.
            </Input>
        """,
    }

    system_message = {
        "role": "system",
        "content": COMPETITOR_COMPANIES_SYSTEM_PROMPT,
    }

    response = await invoke(
        messages=[system_message, user_message],
        model="openai/gpt-4.1",
        temperature=0,
        fallbacks=["anthropic/claude-sonnet-4-latest"],
    )
    response = post_process_gpt_output(response)
    return response


async def get_competitor(company, company_data, company_size):

    user_message = {
        "role": "user",
        "content": COMPETITOR_COMPANIES_POPULAR_USER_PROMPT
        + f"""
            <Input>
                This is company name: {company}. 
                This is company data: {company_data}. 
                This is company size: {company_size}.
            </Input>
        
        """,
    }

    system_message = {
        "role": "system",
        "content": COMPETITOR_COMPANIES_SYSTEM_PROMPT,
    }

    response = await invoke(
        messages=[system_message, user_message],
        model="openai/gpt-4.1",
        temperature=0,
        fallbacks=["anthropic/claude-sonnet-4-latest"],
    )
    response = post_process_gpt_output(response)
    return response


async def company_size_prediction(universal_name):
    if not universal_name:
        return None

    system_message = {
        "role": "system",
        "content": COMPANY_SIZE_PREDICTION_SYSTEM_PROMPT,
    }

    user_message = {
        "role": "user",
        "content": COMPANY_SIZE_PREDICTION_USER_PROMPT
        + f"""
            <Input>
                This is company name: {universal_name}
            </Input>
        """,
    }

    response = await invoke(
        messages=[system_message, user_message],
        model="openai/gpt-4o-mini",
        temperature=0,
        fallbacks=["anthropic/claude-sonnet-4-latest"],
    )

    gpt_output = response.strip()
    response = post_process_gpt_output(gpt_output)

    try:
        company_size = int(response)
        if company_size < 0:
            company_size = -1
    except (ValueError, TypeError):
        company_size = -1

    return company_size


async def determine_company_size(company_name, client):
    company_data = await count_search_results(company_name, client)

    if not company_data or not isinstance(company_data, dict):
        staff_count = await company_size_prediction(company_name)
    else:
        staff_count = company_data.get("li_staffcount") or company_data.get("li_size")

        if not staff_count:
            staff_count = await company_size_prediction(company_name)

    try:
        staff_count = int(staff_count)
    except (ValueError, TypeError):
        print(f"Invalid staff count or company size format for {company_name}")
        return None

    if staff_count >= 100000:
        return "giant_company"
    elif staff_count >= 10000:
        return "large_company"
    elif staff_count >= 5000:
        return "mid_size_company"
    elif staff_count >= 500:
        return "small_medium_enterprise"
    elif staff_count >= 50:
        return "small_company"
    else:
        return "micro_enterprise"
