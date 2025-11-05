from qutils.llm.asynchronous import invoke
from typing import List, Tuple
import re
import os
import json
from elasticsearch import AsyncElasticsearch
from app.utils.outreach.services.ai_template_services.prompts import (
    SYSTEM_PROMPT_QUICK,
    SYSTEM_PROMPT_EXTENSIVE,
    SYSTEM_PROMPT_STANDARD,
)
from copy import deepcopy
import asyncio


async def get_profile(
    search_ids: List[str],
    client: AsyncElasticsearch,
    search_term: str = "_id",
    additional_source: List[str] = [],
) -> List:
    # print(f"GET PROFILE CALLED FOR {search_ids} on search term = {search_term}")
    data = []
    results = await client.search(
        body={
            # "_source": [
            #     "li_name",
            #     "li_urn",
            #     "li_staffcount",
            #     "li_size",
            #     "li_industries",
            #     "li_confirmedlocations",
            #     "li_universalname",
            #     "cb_stock_symbol",
            # ]
            # + additional_source,
            "query": {"terms": {search_term: search_ids}},
        },
        index=os.getenv("ES_PROFILES_INDEX"),
        size=len(search_ids),
    )
    try:
        for es_result in results["hits"]["hits"]:
            profile = es_result.get("_source", [])
            if profile:
                headline = profile.get("headline", "")
                if not headline:
                    experience = profile.get("experience", [])
                    if experience:
                        headline = experience[0].get("profile_headline", "")
                    if not headline:
                        headline = experience[0].get("title", "")
            data.append(headline)
        data = [i for i in data if data]
        # es_result = result["hits"]["hits"][0]
        # experience = es_result["_source"].get("experience", [])
        # headline =
    except Exception as e:
        raise e
    return data


def extract_generic(start: str, end: str, text: str):
    match = re.search(rf"{start}(.*?){end}", text, re.DOTALL)
    return match.group(1) if match else None


async def ai_generated_campaign(
    assignment_name: str,
    total_profiles: int,
    sample_profiles: List[str],
    channel_credits: dict,
    creation_day: str,
    es_client: AsyncElasticsearch,
    sender_data: str,
    search_term: str = "_id",
    override_sample: bool = False,
    profile_data: List[str] = None,
) -> Tuple[str, List[dict]]:

    days_until_saturday = {
        "monday": 5,
        "tuesday": 4,
        "wednesday": 3,
        "thursday": 2,
        "friday": 1,
        "saturday": 0,
        "sunday": -1,
    }

    weekdays = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    all_day_keys = weekdays + [day.capitalize() for day in weekdays]

    creation_day_to_weekend_map = {}

    for day_key in all_day_keys:
        base_day = day_key.lower()
        saturday_offset = days_until_saturday[base_day]
        weekend_days = []

        for i in range(5):
            sat_day = saturday_offset + i * 7
            sun_day = sat_day + 1
            weekend_days.append(f"day_{sat_day}")
            weekend_days.append(f"day_{sun_day}")

        creation_day_to_weekend_map[day_key] = weekend_days

    days_offset = [2, 4, 10]

    creation_day = creation_day.strip()

    system_prompt_quick = deepcopy(SYSTEM_PROMPT_QUICK)
    system_prompt_standard = deepcopy(SYSTEM_PROMPT_STANDARD)
    system_prompt_extensive = deepcopy(SYSTEM_PROMPT_EXTENSIVE)

    channels = "\n".join(f"- {k}" for k, v in channel_credits.items())
    user_prompt = f"""<available_channels>\n{channels}\n</available_channels>\n"""
    if override_sample:
        profile_data = await get_profile(sample_profiles[:5], es_client, search_term)
    user_prompt += f"""<assignment_name> {assignment_name} </assignment_name>\n"""
    if profile_data:
        profile_data = "\n".join(profile_data)
        user_prompt += (
            f"""<sample_profile_data>\n{profile_data}\n</sample_profile_data>\n"""
        )
    user_prompt += f"""<day_today> {creation_day} </day_today>\n"""
    # if sender_data:
    #     user_prompt += f"""<sender_data> {sender_data} </sender_data>\n"""

    # print(user_prompt)

    tasks = []
    system_prompts_lst = [
        system_prompt_quick,
        system_prompt_standard,
        system_prompt_extensive,
    ]
    provider_list = ["openai", "openai", "openai"]
    models_lst = ["gpt-4.1-mini", "gpt-4.1", "gpt-4.1"]

    for i in range(3):
        chat = [
            {"role": "system", "content": system_prompts_lst[i]},
            {
                "role": "user",
                "content": user_prompt
                + f"""\n<important_for_calculation>\n- In order to assist you, I'm giving you days of the upcoming {days_offset[i]//2} Weekends.\n- {", ".join(creation_day_to_weekend_map[creation_day][:days_offset[i]])}\n</important_for_calculation>\n"""
                + "\nIt is important that there are no comments in the output",
            },
        ]

        tasks.append(
            invoke(
                messages=chat,
                model="openai/" + models_lst[i],
                temperature=0.3,
            )
        )

    quick, standard, extensive = await asyncio.gather(*tasks)

    quick_plan = extract_generic("<plan>", "</plan>", quick)
    quick_rationale = extract_generic("<rationale>", "</rationale>", quick)
    standard_plan = extract_generic("<plan>", "</plan>", standard)
    standard_rationale = extract_generic("<rationale>", "</rationale>", standard)
    extensive_plan = extract_generic("<plan>", "</plan>", extensive)
    extensive_rationale = extract_generic("<rationale>", "</rationale>", extensive)

    try:
        quick_plan = json.loads(quick_plan)
    except Exception as e:
        print(e)
        print(quick)

    try:
        standard_plan = json.loads(standard_plan)
    except Exception as e:
        print(e)
        print(standard)

    try:
        extensive_plan = json.loads(extensive_plan)
    except Exception as e:
        print(e)
        print(extensive)

    final_dct = {
        "quick": {"rationale": quick_rationale, "plan": quick_plan},
        "standard": {"rationale": standard_rationale, "plan": standard_plan},
        "extensive": {"rationale": extensive_rationale, "plan": extensive_plan},
    }

    return final_dct
