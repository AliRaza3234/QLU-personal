import os
import anthropic, asyncio

from app.utils.aisearch_final.prompts import *
from app.utils.aisearch_expansion_variants.company_gen import dual_strategies_v2
from app.utils.aisearch_expansion_variants.prompts import *

# from qutils.llm.utilities import asynchronous_llm
from qutils.llm.asynchronous import invoke
import json

client = anthropic.AsyncAnthropic(
    api_key=os.getenv("ANTHROPIC_KEY"),
)


def distribute_five_slices(current_size, past_size, both_size):
    total_slices = 5
    groups = [
        ("current", current_size),
        ("past", past_size),
        ("both", both_size),
    ]
    non_empty = [(name, sz) for (name, sz) in groups if sz > 0]

    if len(non_empty) == 0:
        return (1, 1, 1)

    if len(non_empty) == 1:
        name, _ = non_empty[0]
        return (
            5 if name == "current" else 0,
            5 if name == "past" else 0,
            5 if name == "both" else 0,
        )

    leftover = total_slices

    allocation = {"current": 0, "past": 0, "both": 0}

    non_empty_sorted = sorted(non_empty, key=lambda x: x[1])

    not_filled = []
    for name, size in non_empty_sorted:
        if leftover > size:
            allocation[name] = size
            leftover -= size
        else:
            not_filled.append((name, size))

    if leftover > 0 and len(not_filled) > 0:
        total_capacity = sum(sz for (_, sz) in not_filled)

        ratio_alloc = []
        for name, size in not_filled:
            frac = (size / total_capacity) * leftover
            ratio_alloc.append((name, size, frac))

        floored = [(n, s, int(f)) for (n, s, f) in ratio_alloc]
        sum_floor = sum(x[2] for x in floored)
        leftover_after_floor = leftover - sum_floor

        for n, s, f_int in floored:
            allocation[n] += f_int

        if leftover_after_floor > 0:
            fractional_parts = []
            for i, (n, s, f) in enumerate(ratio_alloc):
                f_int = floored[i][2]
                if f_int < s:  # still room under capacity
                    fractional_parts.append((f - f_int, n))

            fractional_parts.sort(reverse=True, key=lambda x: x[0])

            idx = 0
            while leftover_after_floor > 0 and idx < len(fractional_parts):
                frac_part, n = fractional_parts[idx]
                if allocation[n] < [sz for (nm, sz) in groups if nm == n][0]:
                    allocation[n] += 1
                    leftover_after_floor -= 1
                idx += 1

    for name, size in non_empty:
        if allocation[name] > size:
            allocation[name] = size

    allocation["current"] = int(allocation["current"])
    allocation["past"] = int(allocation["past"])
    allocation["both"] = int(allocation["both"])

    if not allocation["current"] and current_size:
        allocation["current"] = 1
    if not allocation["past"] and past_size:
        allocation["past"] = 1
    if not allocation["both"] and both_size:
        allocation["both"] = 1

    return (allocation["current"], allocation["past"], allocation["both"])


async def llms(messages, model):
    retries = 3
    for i in range(retries):
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
                    temperature=0.1,
                    model="anthropic/claude-3-5-haiku-latest",
                    fallbacks=["openai/gpt-4o", "openai/gpt-4.1"],
                )
            else:
                return None

            return response
        except:
            pass


def structure_titles(titles_dict, event, minn, maxx):
    # minn = str(minn)
    # maxx = str(maxx)
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


def structure_titles_or(titles_dict):
    current_obj = titles_dict.get("current", [])
    past_obj = titles_dict.get("past", [])

    current = []
    past = []

    minn = 1000
    maxx = 0

    for obj in current_obj:
        obj["min"] = int(obj["min"])
        obj["max"] = int(obj["max"])
        current.append(obj["name"])
        if obj["min"] < minn:
            minn = obj["min"]
        if obj["max"] > maxx:
            maxx = obj["max"]

    for obj in past_obj:
        obj["min"] = int(obj["min"])
        obj["max"] = int(obj["max"])
        past.append(obj["name"])
        if obj["min"] < minn:
            minn = obj["min"]
        if obj["max"] > maxx:
            maxx = obj["max"]

    title_output = {}

    for title in current:
        title_output[title] = {"type": "CURRENT", "min": minn, "max": maxx}
    for title in past:
        if title in title_output:
            title_output[title] = {"type": "BOTH", "min": minn, "max": maxx}
        else:
            title_output[title] = {"type": "CURRENT", "min": minn, "max": maxx}

    return {"title": {"event": "OR", "filter": title_output}}


def structure_locations(locations_dict, event, current_locations, past_locations):
    current = locations_dict.get("current", [])
    past = locations_dict.get("past", [])

    if current and not past:
        if past_locations:
            past = past_locations
    if past and not current:
        if current_locations:
            current = current_locations

    if current:
        current += [item for item in current_locations if item not in current]
    if past:
        past += [item for item in past_locations if item not in past]

    location_output = {}

    if event == "CURRENT":
        for title in current:
            location_output[title] = {"type": "CURRENT"}
    elif event == "PAST":
        for title in past:
            location_output[title] = {"type": "PAST"}
    else:
        for title in current:
            location_output[title] = {"type": "CURRENT"}
        for title in past:
            if title not in location_output:
                location_output[title] = {"type": "PAST"}
            else:
                location_output[title] = {"type": "BOTH"}

    return {"event": event, "filter": location_output}


def structure_industries(industries_dict, event):
    current = industries_dict.get("current", [])
    past = industries_dict.get("past", [])
    industry_output = {}

    if event == "CURRENT":
        for title in current:
            industry_output[title] = {"type": "CURRENT", "exclusion": False}
    elif event == "PAST":
        for title in past:
            industry_output[title] = {"type": "PAST", "exclusion": False}
    else:
        for title in current:
            industry_output[title] = {"type": "CURRENT", "exclusion": False}
        for title in past:
            if title in industry_output:
                industry_output[title] = {"type": "BOTH", "exclusion": False}
            else:
                industry_output[title] = {"type": "PAST", "exclusion": False}

    return {"event": event, "filter": industry_output}


async def titles_expansion(titles, queries, titleEvent):
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

    for i in range(3):
        # try:
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
        structured_response = {
            "title": structure_titles(response_data, titleEvent, minn, maxx)
        }
        return structured_response


async def locations_expansion(locations):
    current_locations = locations.get("current", [])
    past_locations = locations.get("past", [])

    user_prompt = (
        LOCATIONS_EXPANSION_USER_PROMPT
        + f"""
<locations>
current = {current_locations},
past = {past_locations}
</locations>
                    """
    )

    messages = [
        {"role": "system", "content": LOCATIONS_EXPANSION_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    for i in range(3):
        try:
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
            structured_response = {
                "location": structure_locations(
                    response_data, locations["event"], current_locations, past_locations
                )
            }
            return structured_response
        except Exception as e:
            print(e)
            pass


async def collect_with_timeout(generator, timeout=30):
    collected_values = []

    async def collect():
        async for value in generator:
            collected_values.append(value)

    try:
        await asyncio.wait_for(collect(), timeout)
    except asyncio.TimeoutError:
        pass

    return collected_values


async def dual_agent(query, timeline, es_client):
    if timeline == "current":
        current_prompt = query
    else:
        current_prompt = ""

    if timeline == "past":
        past_prompt = query
    else:
        past_prompt = ""

    collected_values = await collect_with_timeout(
        dual_strategies_v2(current_prompt, past_prompt, es_client)
    )
    return collected_values


def format_industries(selected_industries, oldCompanies=None, size=1):
    if not selected_industries:
        return []

    n = len(selected_industries)
    if n <= size:
        group_count = n
    else:
        group_count = size

    base_size = n // group_count
    remainder = n % group_count

    groups = []
    start = 0
    for i in range(group_count):
        current_size = base_size + (1 if i < remainder else 0)
        chunk = selected_industries[start : start + current_size]
        groups.append(chunk)
        start += current_size

    prompts = []
    for chunk in groups:
        industries_text = ", ".join(f"{industry} industry" for industry in chunk)
        prompt = f"Generate me a list of companies from the following industries:\n{industries_text}"
        if oldCompanies:
            prompt += f"\n\nDon't generate any of these companies:\n{oldCompanies}"
        prompts.append(prompt)

    return prompts


async def variants(data, queries, es_client):
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
    locations = (
        {
            "current": (
                [
                    location
                    for location, details in data["location"]["filter"].items()
                    if details["type"] == "CURRENT" or details["type"] == "BOTH"
                ]
                if data["location"]
                else []
            ),
            "past": (
                [
                    location
                    for location, details in data["location"]["filter"].items()
                    if details["type"] == "PAST" or details["type"] == "BOTH"
                ]
                if data["location"]
                else []
            ),
            "event": (data["location"]["event"] if data["location"] else None),
        }
        if data.get("location", {})
        else {}
    )
    final = {
        "company": None,
        "industry_company": None,
        "title_or": None,
        "title_expansion": None,
        "location_expansion": None,
    }

    companies = data.get("companies", {})
    selected_industries = data.get("selectedIndustries", {})
    titles_expanded_or_not = data.get("titlesExpanded")

    currentTotalCompanies = []
    pastTotalCompanies = []

    compNamesPast = []
    compNamesCurr = []

    for item in companies.get("current", []):
        for obj in item.get("pills", []):
            if obj.get("state", "") == "selected":
                currentTotalCompanies.append(obj.get("id", None))
                if obj.get("name", None):
                    compNamesCurr.append(obj.get("name", None))

    for item in companies.get("past", []):
        for obj in item.get("pills", []):
            if obj.get("state", "") == "selected":
                pastTotalCompanies.append(obj.get("id", None))
                if obj.get("name", None):
                    compNamesPast.append(obj.get("name", None))

    tasks = []

    both_industries = [
        item
        for item in selected_industries.get("current", [])
        if item in selected_industries.get("past", [])
    ]
    current_industries = [
        item
        for item in selected_industries.get("current", [])
        if item not in both_industries
    ]
    past_industries = [
        item
        for item in selected_industries.get("past", [])
        if item not in both_industries
    ]

    num = 0
    past_num = 0
    both_num = 0
    # print(len(current_industries), len(past_industries), len(both_industries))
    currSize, pastSize, bothSize = distribute_five_slices(
        len(current_industries), len(past_industries), len(both_industries)
    )
    # print(currSize, pastSize, bothSize)
    if current_industries:
        industries_strings = format_industries(
            selected_industries.get("current"), compNamesCurr, currSize
        )
        tasks = [
            asyncio.create_task(dual_agent(ind, "current", es_client))
            for ind in industries_strings
        ]
        num += len(tasks)
    if past_industries:
        industries_strings = format_industries(
            selected_industries.get("past"), compNamesPast, pastSize
        )
        tasks.extend(
            [
                asyncio.create_task(dual_agent(ind, "past", es_client))
                for ind in industries_strings
            ]
        )
        past_num += len(tasks)

    if both_industries:
        industries_strings = format_industries(
            selected_industries.get("current"), compNamesCurr, bothSize
        )
        tasks.extend(
            [
                asyncio.create_task(dual_agent(ind, "current", es_client))
                for ind in industries_strings
            ]
        )
        both_num += len(tasks)

    loc_flag = False
    if locations:
        loc_flag = True
        tasks.append(locations_expansion(locations))

    if titles:
        if titles.get("event", "") != "OR" and (
            not companies
            or companies.get("event") == titles.get("event")
            or companies.get("event", "") == "OR"
        ):
            titles_or = structure_titles_or(titles)
            final.update({"title_or": titles_or})
            titles["event"] = "OR"

        # elif (
        #     titles.get("event", "") == "OR"
        #     and companies
        #     and not companies.get("event", "") == "OR"
        # ):
        #     titles_or = structure_titles_or(titles)
        #     final.update({"title_or": titles_or})
        #     titles["event"] = "OR"

    title_flag = False
    if titles and not titles_expanded_or_not:
        title_flag = True
        tasks.append(titles_expansion(titles, queries, titles["event"]))

    company_extracted = []
    if tasks:
        company_extracted = await asyncio.gather(*tasks)
        if title_flag:
            titles_exp = company_extracted[-1]
            company_extracted.pop()
            if titles_exp and titles_exp.get("title", {}).get("filter", {}):
                final.update({"title_expansion": titles_exp})
        if loc_flag:
            location = company_extracted[-1]
            company_extracted.pop()
            if location and location.get("location", {}).get("filter", {}):
                final.update({"location_expansion": location})

    if company_extracted:
        temp_company = {
            "companiesCurrent": [
                json.loads(item[item.find("{") : item.rfind("}") + 1].strip())
                for sublist in company_extracted[:num]
                for item in sublist
            ],
            "companiesPast": [
                json.loads(item[item.find("{") : item.rfind("}") + 1].strip())
                for sublist in company_extracted[num : num + past_num]
                for item in sublist
            ],
            "event": companies.get("event", "OR"),
        }
        both = [
            json.loads(item[item.find("{") : item.rfind("}") + 1].strip())
            for sublist in company_extracted[num + past_num :]
            for item in sublist
        ]
        temp_company["companiesCurrent"].extend(both)
        temp_company["companiesPast"].extend(both)

        tempCurrent = []
        for dictt in temp_company.get("companiesCurrent", []):
            if dictt not in tempCurrent:
                tempCurrent.append(dictt)
        tempPast = []
        for dictt in temp_company.get("companiesPast", []):
            if dictt not in tempPast:
                tempPast.append(dictt)

        for index in range(len(tempCurrent) - 1, -1, -1):
            if (
                tempCurrent[index].get("es_data", {}).get("es_id", -1)
                in currentTotalCompanies
            ) or (tempCurrent[index].get("excluded", False)):
                tempCurrent.pop(index)

        for index in range(len(tempPast) - 1, -1, -1):
            if (
                tempPast[index].get("es_data", {}).get("es_id", -1)
                in pastTotalCompanies
            ) or (tempPast[index].get("excluded", False)):
                tempPast.pop(index)

        if (tempCurrent or tempPast) and (len(tempCurrent) + len(tempPast)) > 2:
            final["company"] = (
                {
                    "companiesCurrent": tempCurrent,
                    "companiesPast": tempPast,
                    "event": companies.get("event", "OR"),
                }
                if tempCurrent or tempPast
                else None
            )

    if selected_industries.get("current") or selected_industries.get("past"):
        final["industry_company"] = {
            "industry": structure_industries(
                selected_industries, companies.get("event", "OR")
            )
        }

    return final
