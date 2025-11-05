import asyncio

from app.utils.aisearch_expansion_variants.prompts import (
    INDUSTRIES_SUGGESTION_USER_PROMPT,
    INDUSTRIES_SUGGESTION_SYSTEM_PROMPT,
    TITLES_EXPANSION_USER_PROMPT,
    TITLES_EXPANSION_SYSTEM_PROMPT,
)

from qutils.llm.asynchronous import invoke
from qutils.llm.agents.industry import breakdown


async def llms(messages, model):
    retries = 3
    for _ in range(retries):
        try:
            if model == "openai":
                response = await invoke(
                    messages=messages,
                    temperature=0.1,
                    model="openai/gpt-4o",
                    fallbacks=["openai/gpt-4.1", "anthropic/claude-3-7-sonnet-latest"],
                )
            elif model == "anthropic":
                response = await invoke(
                    messages=messages,
                    temperature=0,
                    model="anthropic/claude-sonnet-4-20250514",
                    fallbacks=["anthropic/claude-3-7-sonnet-latest", "openai/gpt-4.1"],
                )
            else:
                return None

            return response
        except:
            pass


def structure_industries(industries_dict, event):
    current = industries_dict.get("current", [])
    past = industries_dict.get("past", [])
    industry_output = {}

    if event == "CURRENT":
        for industry in current:
            industry_output[industry.title()] = {"type": "CURRENT", "exclusion": False}
    elif event == "PAST":
        for industry in current:
            industry_output[industry.title()] = {"type": "PAST", "exclusion": False}
        for industry in past:
            industry_output[industry.title()] = {"type": "PAST", "exclusion": False}
    else:
        for industry in current:
            industry_output[industry.title()] = {"type": "CURRENT", "exclusion": False}
        for industry in past:
            if industry in industry_output:
                industry_output[industry.title()] = {"type": "BOTH", "exclusion": False}
            else:
                industry_output[industry.title()] = {"type": "PAST", "exclusion": False}

    return {"event": event, "filter": industry_output}


def structure_titles(titles_dict, event, minn, maxx):
    current = titles_dict.get("current", [])
    past = titles_dict.get("past", [])
    title_output = {}

    if event == "CURRENT":
        for title in current:
            title_output[title] = {"type": "CURRENT", "min": minn, "max": maxx}
    elif event == "PAST":
        for title in past:
            title_output[title] = {"type": "PAST", "min": minn, "max": maxx}
    else:
        for title in current:
            title_output[title] = {"type": "CURRENT", "min": minn, "max": maxx}
        for title in past:
            if title not in title_output:
                title_output[title] = {"type": "PAST", "min": minn, "max": maxx}
            else:
                title_output[title] = {"type": "BOTH", "min": minn, "max": maxx}

    return {"event": event, "filter": title_output}


def create_filter_structure(current_industries, past_industries, event):
    industry_filter = {"industry": {"event": event.upper(), "filter": {}}}

    event_upper = event.upper()

    if event_upper == "CURRENT":
        for industry in current_industries:
            industry_filter["industry"]["filter"][industry] = {
                "type": "CURRENT",
                "exclusion": False,
            }

    elif event_upper == "PAST":
        for industry in past_industries:
            industry_filter["industry"]["filter"][industry] = {
                "type": "PAST",
                "exclusion": False,
            }

    elif event_upper == "OR":
        all_industries = current_industries + past_industries
        for industry in all_industries:
            industry_filter["industry"]["filter"][industry] = {
                "type": "CURRENT",
                "exclusion": False,
            }

    elif event_upper == "AND":
        for industry in current_industries:
            if industry in past_industries:
                industry_filter["industry"]["filter"][industry] = {
                    "type": "BOTH",
                    "exclusion": False,
                }
            else:
                industry_filter["industry"]["filter"][industry] = {
                    "type": "CURRENT",
                    "exclusion": False,
                }
        for industry in past_industries:
            if industry in current_industries:
                industry_filter["industry"]["filter"][industry] = {
                    "type": "BOTH",
                    "exclusion": False,
                }
            else:
                industry_filter["industry"]["filter"][industry] = {
                    "type": "PAST",
                    "exclusion": False,
                }
    else:
        raise ValueError("Event must be one of 'CURRENT', 'PAST', 'OR', or 'AND'")

    return industry_filter


async def industries_figuring(companies):
    current_companies = []
    past_companies = []

    current_companies_prompt = ""
    for big_obj in companies.get("current", {}):
        for obj in big_obj.get("pills"):
            if obj["state"] == "selected":
                current_companies.append(obj["universalName"])
        current_companies_prompt += big_obj["prompt"]

    past_companies_prompt = ""
    for big_obj in companies.get("past", {}):
        for obj in big_obj.get("pills"):
            if obj["state"] == "selected":
                past_companies.append(obj["universalName"])
        past_companies_prompt += big_obj["prompt"]

    event = companies["event"]
    current_industries = []
    past_industries = []
    if event == "AND":
        current_industries, past_industries = await asyncio.gather(
            *[
                breakdown(current_companies_prompt),
                breakdown(past_companies_prompt),
            ]
        )
    elif event == "OR":
        current_industries = await breakdown(current_companies_prompt, num_industries=7)
    elif event == "CURRENT":
        current_industries = await breakdown(current_companies_prompt, num_industries=7)
    elif event == "PAST":
        past_industries = await breakdown(current_companies_prompt, num_industries=7)

    industry_filter = create_filter_structure(
        current_industries, past_industries, event
    )
    return industry_filter


async def titles_expansion(titles, queries):
    current_obj = titles.get("current", [])
    past_obj = titles.get("past", [])

    current_titles = []
    past_titles = []

    minn = 1000
    maxx = 0

    for obj in current_obj:
        obj["min"] = int(obj["min"])
        obj["max"] = int(obj["max"])
        current_titles.append(obj["name"])
        if obj["min"] < minn:
            minn = obj["min"]
        if obj["max"] > maxx:
            maxx = obj["max"]

    for obj in past_obj:
        obj["min"] = int(obj["min"])
        obj["max"] = int(obj["max"])
        past_titles.append(obj["name"])
        if obj["min"] < minn:
            minn = obj["min"]
        if obj["max"] > maxx:
            maxx = obj["max"]

    user_prompt = (
        TITLES_EXPANSION_USER_PROMPT
        + f"""
<All_user_queries>
    {queries} # All queries are in order (the last being the latest)
</All_user_queries>
<Titles>
current = {current_titles},
past = {past_titles}
</Titles>
                    """
    )

    messages = [
        {"role": "system", "content": TITLES_EXPANSION_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    for _ in range(3):
        response = await llms(messages, "anthropic")
        response_content = (
            response[response.rfind("<Output>") : response.rfind("</Output>")]
            .replace("<Output>", "")
            .replace("<", "")
        )
        response = response_content[
            response_content.find("{") : response_content.rfind("}") + 1
        ]
        response_data = eval(
            response_content[
                response_content.find("{") : response_content.rfind("}") + 1
            ]
        )
        if response_data.get("current", []):
            response_data["current"] += current_titles
        if response_data.get("past", []):
            response_data["past"] += past_titles
        structured_response = {
            "title": structure_titles(response_data, titles["event"], minn, maxx)
        }
        return structured_response


async def expansion(data, queries, es_client):
    titles = (
        {
            "current": (
                [
                    {
                        "name": title,
                        "min": details["min"],
                        "max": details["max"],
                    }
                    for title, details in data["title"]["filter"].items()
                    if details["type"] == "CURRENT" or details["type"] == "BOTH"
                ]
                if data["title"]
                else []
            ),
            "past": (
                [
                    {
                        "name": title,
                        "min": details["min"],
                        "max": details["max"],
                    }
                    for title, details in data["title"]["filter"].items()
                    if details["type"] == "PAST" or details["type"] == "BOTH"
                ]
                if data["title"]
                else []
            ),
            "event": (data["title"]["event"] if data["title"] else None),
        }
        if data.get("title", {})
        else {}
    )

    industries = data.get("industry", {})
    companies = data.get("companies", {})

    if companies and not industries:
        industries = await industries_figuring(companies)
        if industries:
            if industries.get("industry", {}).get("filter", {}):
                return industries

    if titles:
        titles = await titles_expansion(titles, queries)
        if titles:
            if titles.get("title", {}).get("filter", {}):
                return titles

    return {}


async def industry_suggestions(data, queries, es_client):
    companies = data.get("companies", {})
    industries = {}
    if companies:
        industries = await industries_figuring_suggestions(
            companies, queries, companies.get("event", ""), es_client
        )
        if industries:
            if companies.get("event", "") == "PAST":
                if industries.get("current", []):
                    industries["past"] += industries["current"]
                industries["current"] = []
            elif companies.get("event", "") == "CURRENT":
                industries["past"] = []
            elif companies.get("event", "") == "OR":
                industries["current"] = industries.get("current", []) + industries.get(
                    "past", []
                )
                industries["current"] = list(set(industries["current"]))
                industries["past"] = []

    if len(industries.get("current", [])) > 30:
        industries["current"] = industries["current"][:30]
    if len(industries.get("past", [])) > 30:
        industries["past"] = industries["past"][:30]

    if industries.get("current", []):
        industries["current"] = [item.title() for item in industries.get("current", [])]

    if industries.get("past", []):
        industries["past"] = [item.title() for item in industries.get("past", [])]
    return industries


async def industries_figuring_suggestions(companies, queries, event, connection):
    current_companies = []
    past_companies = []

    current_companies_prompt = ""
    for big_obj in companies.get("current", {}):
        for obj in big_obj.get("pills"):
            if obj["state"] == "selected":
                current_companies.append(obj["universalName"])
        current_companies_prompt += big_obj["prompt"]

    past_companies_prompt = ""
    for big_obj in companies.get("past", {}):
        for obj in big_obj.get("pills"):
            if obj["state"] == "selected":
                past_companies.append(obj["universalName"])
        past_companies_prompt += big_obj["prompt"]

    complete_companies = current_companies + past_companies
    if not complete_companies:
        return {}

    if companies["event"] == "OR":
        current_companies = complete_companies
        past_companies = []

    query = {
        "size": 10000,
        "_source": ["li_industries", "li_specialties", "li_universalname"],
        "query": {"terms": {"li_universalname": complete_companies}},
    }
    results = await connection.search(body=query, index="company", timeout="60s")
    results = results["hits"]["hits"]

    current_industries = []
    past_industries = []
    for result in results:
        result_industries = (
            [item for item in result["_source"]["li_industries"]]
            if isinstance(result["_source"]["li_industries"], list)
            else []
        )
        result_specialties = (
            [item for item in result["_source"]["li_specialties"]]
            if isinstance(result["_source"]["li_specialties"], list)
            else []
        )

        current_industries += (
            result_industries + result_specialties
            if result["_source"]["li_universalname"] in current_companies
            else []
        )
        past_industries += (
            result_industries + result_specialties
            if result["_source"]["li_universalname"] in past_companies
            else []
        )

    currentString = (
        f"""current = {set(current_industries)}, description = {current_companies_prompt}"""
        if current_industries
        else ""
    )
    pastString = (
        f"""past = {set(past_industries)}, description = {past_companies_prompt}"""
        if past_industries
        else ""
    )

    user_prompt = (
        INDUSTRIES_SUGGESTION_USER_PROMPT
        + f"""
<All_user_queries>
    {queries} # All queries are in order (the last being the latest)
</All_user_queries>
<Industries>
    {currentString}
    {pastString}
</Industries>
"""
    )

    for _ in range(3):
        try:
            messages = [
                {"role": "system", "content": INDUSTRIES_SUGGESTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
            response = await llms(messages, "anthropic")
            response_content = (
                response[response.rfind("<Output>") : response.rfind("</Output>")]
                .replace("<Output>", "")
                .replace("<", "")
            )
            response = response_content[
                response_content.find("{") : response_content.rfind("}") + 1
            ]
            response_data = eval(
                response_content[
                    response_content.find("{") : response_content.rfind("}") + 1
                ]
            )
            cur = response_data.get("current", [])
            pas = response_data.get("past", [])

            flag = True
            if event.lower() == "current":
                if not cur:
                    flag = False
            elif event.lower() == "past":
                if not pas:
                    flag = False
            elif event.lower() == "and":
                if not cur or not pas:
                    flag = False

            if not flag:
                user_prompt = (
                    user_prompt
                    + "\nBe careful regarding the output for BOTH, current and past, as required."
                )
                continue
            return response_data
        except Exception as e:
            pass
    return {
        "current": list(set(current_industries)),
        "past": list(set(past_industries)),
    }
