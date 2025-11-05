import asyncio, json, time, re, sys, os, copy, traceback
from app.utils.qlu2_features.aisearch.suggestions.suggestions_prompts import (
    MERGED_EXPANSION_SYSTEM,
    MERGED_EXPANSION_USER,
    COMPANY_MULTIPLE_STREAM_PROMPTS_SYSTEM,
    COMPANY_MULTIPLE_STREAM_PROMPTS_USER,
    TITLES_EXPANSION_SYSTEM_PROMPT,
    TITLES_EXPANSION_USER_PROMPT,
    MUST_INCLUDE_SKILLS_PROMPT_SYSTEM,
    MUST_INCLUDE_SKILLS_PROMPT_USER,
    PRECISION_SUGGESTIONS_PROMPT_SYSTEM,
    PRECISION_SUGGESTIONS_PROMPT_USER,
    INDUSTRY_TIMELINE_DECIDER_SYSTEM,
    INDUSTRY_TIMELINE_DECIDER_USER,
    # Flag Agents Prompts
    COMP_STREAM_BLOCKED_FLAG_SYSTEM,
    COMP_STREAM_BLOCKED_FLAG_USER,
    INDUSTRY_BLOCKED_FLAG_SYSTEM,
    INDUSTRY_BLOCKED_FLAG_USER,
    TITLES_MANAGEMENT_LEVELS_BLOCKED_FLAG_SYSTEM,
    TITLES_MANAGEMENT_LEVELS_BLOCKED_FLAG_USER,
    TIMELINE_BLOCKED_FLAG_SYSTEM,
    TIMELINE_BLOCKED_FLAG_USER,
    EXPERIENCE_TENURES_EDUCATION_BLOCKED_FLAG_SYSTEM,
    EXPERIENCE_TENURES_EDUCATION_BLOCKED_FLAG_USER,
    SIMPLE_SUGGESTION_MESSAGE_USER,
    SIMPLE_SUGGESTION_MESSAGE_SYSTEM,
    AI_SEARCH_MULTIPLE_STREAMS_SYSTEM,
    AI_SEARCH_MULTIPLE_STREAMS_USER,
)
from app.utils.qlu2_features.aisearch.utilities.llm_functions.llms import (
    call_llama_70b,
    call_gpt_oss_120b,
    call_claude_sonnet,
    call_gpt_4_1,
    call_gpt_4_1_mini,
)
from app.utils.qlu2_features.aisearch.utilities.helper_functions.fs_side_functions import (
    map_locations_by_name,
)
from app.utils.qlu2_features.aisearch.utilities.helper_functions.postgres_functions import (
    insert_into_cache_single_entity_results,
)
from app.utils.qlu2_features.aisearch.utilities.helper_functions.misc_functions import (
    extract_generic,
)


async def requirements_expansion_agent(failed_query):

    if not failed_query:
        return None

    messages = [
        {"role": "system", "content": MERGED_EXPANSION_SYSTEM},
        {
            "role": "user",
            "content": (MERGED_EXPANSION_USER).replace(
                "{{failed_query}}", failed_query
            ),
        },
    ]

    response = await call_llama_70b(
        messages=messages,
        temperature=1,
    )

    expanded_query = extract_generic("<expanded_query>", "</expanded_query>", response)

    return expanded_query


async def company_multiple_stream_prompts_agent(
    company_description_input, response_id, convId, promptId, prompt, mode="suggestions"
):

    SYSTEM_PROMPT = COMPANY_MULTIPLE_STREAM_PROMPTS_SYSTEM
    USER_PROMPT = COMPANY_MULTIPLE_STREAM_PROMPTS_USER

    if mode != "suggestions":
        SYSTEM_PROMPT = AI_SEARCH_MULTIPLE_STREAMS_SYSTEM
        USER_PROMPT = AI_SEARCH_MULTIPLE_STREAMS_USER

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (USER_PROMPT).replace(
                "{{company_description_input}}", str(company_description_input)
            ),
        },
    ]

    asyncio.create_task(
        insert_into_cache_single_entity_results(
            conversation_id=convId,
            prompt_id=promptId,
            response_id=response_id + 2,
            prompt=prompt,
            result={"comp_stream_messages": copy.deepcopy(messages)},
            temp=True,
        )
    )

    response = await call_gpt_oss_120b(
        messages=messages,
        temperature=0.1,
    )

    output_json = []
    try:
        output_json = json.loads(
            extract_generic("<variants_list>", "</variants_list>", response)
        )
    except (json.JSONDecodeError, ValueError, TypeError):
        output_json = []

    asyncio.create_task(
        insert_into_cache_single_entity_results(
            conversation_id=convId,
            prompt_id=promptId,
            response_id=response_id,
            prompt=prompt,
            result={"output_variants": output_json, "response": response},
            temp=True,
        )
    )

    return output_json


async def comp_stream_blocked_flag_agent(existing_company_prompts):
    messages = [
        {"role": "system", "content": COMP_STREAM_BLOCKED_FLAG_SYSTEM},
        {
            "role": "user",
            "content": COMP_STREAM_BLOCKED_FLAG_USER.replace(
                "{{company_description_input}}", str(existing_company_prompts)
            ),
        },
    ]

    response = await call_gpt_4_1(
        messages=messages,
        temperature=0.1,
    )

    extracted_output = extract_generic(
        "<is_comp_stream_suggestion_blocked>",
        "</is_comp_stream_suggestion_blocked>",
        response,
    )
    if extracted_output:
        extracted_output = extracted_output.strip()
        if extracted_output == "True":
            return True, response
        else:
            return False, response
    else:
        return False, response


async def industry_blocked_flag_agent(existing_company_prompts):

    messages = [
        {"role": "system", "content": INDUSTRY_BLOCKED_FLAG_SYSTEM},
        {
            "role": "user",
            "content": INDUSTRY_BLOCKED_FLAG_USER.replace(
                "{{company_description_input}}", str(existing_company_prompts)
            ),
        },
    ]

    response = await call_gpt_4_1(
        messages=messages,
        temperature=0.1,
    )

    extracted_output = extract_generic(
        "<is_industry_suggestion_blocked>",
        "</is_industry_suggestion_blocked>",
        response,
    )
    if extracted_output:
        extracted_output = extracted_output.strip()
        if extracted_output == "True":
            return True, response
        else:
            return False, response
    else:
        return False, response


async def titles_management_levels_blocked_flag_agent(conversation_context):
    messages = [
        {"role": "system", "content": TITLES_MANAGEMENT_LEVELS_BLOCKED_FLAG_SYSTEM},
        {
            "role": "user",
            "content": TITLES_MANAGEMENT_LEVELS_BLOCKED_FLAG_USER.replace(
                "{{conversation_context}}", str(conversation_context)
            ),
        },
    ]

    response = await call_gpt_4_1(
        messages=messages,
        temperature=0.1,
    )

    extracted_output = extract_generic(
        "<is_management_level_or_job_titles_suggestion_blocked>",
        "</is_management_level_or_job_titles_suggestion_blocked>",
        response,
    )
    if extracted_output:
        extracted_output = extracted_output.strip()
        if extracted_output == "True":
            return True, response
        else:
            return False, response
    else:
        return False, response


async def timeline_blocked_flag_agent(conversation_context):
    messages = [
        {"role": "system", "content": TIMELINE_BLOCKED_FLAG_SYSTEM},
        {
            "role": "user",
            "content": TIMELINE_BLOCKED_FLAG_USER.replace(
                "{{conversation_context}}", str(conversation_context)
            ),
        },
    ]

    response = await call_gpt_4_1(
        messages=messages,
        temperature=0.1,
    )

    extracted_output = extract_generic(
        "<is_timeline_suggestion_blocked>",
        "</is_timeline_suggestion_blocked>",
        response,
    )
    if extracted_output:
        extracted_output = extracted_output.strip()
        if extracted_output == "True":
            return True, response
        else:
            return False, response
    else:
        return False, response


async def experience_tenures_education_blocked_flag_agent(conversation_context):
    messages = [
        {"role": "system", "content": EXPERIENCE_TENURES_EDUCATION_BLOCKED_FLAG_SYSTEM},
        {
            "role": "user",
            "content": EXPERIENCE_TENURES_EDUCATION_BLOCKED_FLAG_USER.replace(
                "{{conversation_context}}", str(conversation_context)
            ),
        },
    ]

    response = await call_gpt_4_1(
        messages=messages,
        temperature=0.1,
    )

    extracted_output = extract_generic(
        "<is_experience_tenures_education_suggestion_blocked>",
        "</is_experience_tenures_education_suggestion_blocked>",
        response,
    )

    if extracted_output:
        extracted_output = extracted_output.strip()
        if extracted_output == "True":
            return True, response
        else:
            return False, response
    else:
        return False, response


async def simple_suggestion_message_agent(conversation_context, suggestion_prompt):
    messages = [
        {"role": "system", "content": SIMPLE_SUGGESTION_MESSAGE_SYSTEM},
        {
            "role": "user",
            "content": SIMPLE_SUGGESTION_MESSAGE_USER.replace(
                "{{suggestion_prompt}}", str(suggestion_prompt)
            ),
        },
    ]

    response = await call_llama_70b(
        messages=messages,
        temperature=0.6,
    )

    return response


async def must_include_skill_keywords_agent(filters, context):
    skill_keywords = filters.get("skill", {}).get("filter", {})

    must_include_keywords = []
    normal_keywords = []

    if skill_keywords:
        for key, value in skill_keywords.items():
            if value.get("state") == "must-include":
                must_include_keywords.append(key)
            else:
                normal_keywords.append(key)

    input_keywords = {
        "must_include_keywords": must_include_keywords,
        "normal_keywords": normal_keywords,
    }

    input_keywords = json.dumps(input_keywords)

    messages = [
        {"role": "system", "content": MUST_INCLUDE_SKILLS_PROMPT_SYSTEM},
        {
            "role": "user",
            "content": MUST_INCLUDE_SKILLS_PROMPT_USER.replace(
                "{{context}}", str(context)
            ).replace("{{keywords}}", str(input_keywords)),
        },
    ]

    response = await call_gpt_4_1_mini(
        messages=messages,
        temperature=1,
    )

    json_output = extract_generic("<json_output>", "</json_output>", response)
    try:
        json_output = json.loads(json_output) if json_output else {}
    except Exception as exception:
        print(f"Error loading JSON: {exception}")
        json_output = {}

    output_keywords = {**filters.get("skill", {}).get("filter", {})}

    relation = filters.get("skill", {}).get("relation", "OR")
    updated_must_included_keywords = []

    for item in json_output.get("must_include_keywords", []):
        updated_must_included_keywords.append(item)
        if item in output_keywords:
            output_keywords[item]["state"] = "must-include"
        else:
            output_keywords[item] = {
                "type": "CURRENT",
                "state": "must-include",
            }

    skills = {
        "skill": {
            "event": "OR",
            "filter": output_keywords,
            "relation": relation,
        }
    }

    return skills, updated_must_included_keywords


async def precise_suggestions_generation(default_count, possible_suggestions):
    messages = [
        {"role": "system", "content": PRECISION_SUGGESTIONS_PROMPT_SYSTEM},
        {
            "role": "user",
            "content": PRECISION_SUGGESTIONS_PROMPT_USER.replace(
                "{{default_count}}", str(default_count)
            ).replace("{{possible_suggestions}}", str(possible_suggestions)),
        },
    ]

    response = await call_gpt_4_1_mini(
        messages=messages,
        temperature=1,
    )

    selected_suggestion = extract_generic(
        "<selected_suggestion>", "</selected_suggestion>", response
    )
    suggestion_message = extract_generic(
        "<suggestion_message>", "</suggestion_message>", response
    )

    if selected_suggestion:
        selected_suggestion = selected_suggestion.strip()
    if suggestion_message:
        suggestion_message = suggestion_message.strip()

    return selected_suggestion, suggestion_message, response


async def industry_timeline_decider_agent(
    industry_keywords, shorten_current_prompts_list, shorten_past_prompts_list
):
    company_agent_output = {
        "current": shorten_current_prompts_list,
        "past": shorten_past_prompts_list,
    }

    messages = [
        {"role": "system", "content": INDUSTRY_TIMELINE_DECIDER_SYSTEM},
        {
            "role": "user",
            "content": INDUSTRY_TIMELINE_DECIDER_USER.replace(
                "{{industry_keywords}}", str(industry_keywords)
            ).replace("{{company_agent_output}}", str(company_agent_output)),
        },
    ]

    response = await call_gpt_4_1(
        messages=messages,
        temperature=1,
    )

    industry_json = extract_generic("<industry_json>", "</industry_json>", response)

    try:
        response_data = json.loads(industry_json)
    except (json.JSONDecodeError, ValueError, TypeError):
        response_data = {}

    return {"industry": response_data}


async def titles_expansion_suggestions_agent(titles, context):

    if not titles or not isinstance(titles, dict) or "filter" not in titles:
        return None, None

    original_titles_keys = titles.get("filter", {}).keys()
    original_titles_event = titles.get("event", None)

    if not original_titles_event:
        return None, None

    current_titles = []
    past_titles = []

    minn = 1000
    maxx = 0

    for key, value in titles.get("filter", {}).items():
        if value.get("type") == "CURRENT":
            current_titles.append(key)
        elif value.get("type") == "PAST":
            past_titles.append(key)
        elif value.get("type") == "BOTH":
            current_titles.append(key)
            past_titles.append(key)

    MAX_VALUE = 500000000000
    MIN_VALUE = -1

    current_min_value = MAX_VALUE
    current_max_value = MIN_VALUE
    past_min_value = MAX_VALUE
    past_max_value = MIN_VALUE

    for title, value in titles.get("filter", {}).items():
        if value.get("type", "") == "CURRENT":
            current_min_value = min(current_min_value, int(value.get("min", MAX_VALUE)))
            current_max_value = max(current_max_value, int(value.get("max", MIN_VALUE)))
        elif value.get("type", "") == "PAST":
            past_min_value = min(past_min_value, int(value.get("min", MAX_VALUE)))
            past_max_value = max(past_max_value, int(value.get("max", MIN_VALUE)))
        elif value.get("type", "") == "BOTH":
            current_min_value = min(current_min_value, int(value.get("min", MAX_VALUE)))
            current_max_value = max(current_max_value, int(value.get("max", MIN_VALUE)))
            past_min_value = min(past_min_value, int(value.get("min", MAX_VALUE)))
            past_max_value = max(past_max_value, int(value.get("max", MIN_VALUE)))

    if current_min_value == MAX_VALUE and current_max_value == MIN_VALUE:
        current_min_value = past_min_value
        current_max_value = past_max_value
    elif past_min_value == MAX_VALUE and past_max_value == MIN_VALUE:
        past_min_value = current_min_value
        past_max_value = current_max_value

    messages = [
        {"role": "system", "content": TITLES_EXPANSION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": TITLES_EXPANSION_USER_PROMPT.replace(
                "{{titles}}",
                str({"current_titles": current_titles, "past_titles": past_titles}),
            ).replace("{{context}}", str(context)),
        },
    ]

    # try:
    response = await call_gpt_4_1(
        messages=messages,
        temperature=0.6,
    )

    titles_json = extract_generic("<titles_json>", "</titles_json>", response)

    expanded_titles = {}

    try:
        expanded_titles = json.loads(titles_json)
    except (json.JSONDecodeError, ValueError, TypeError):
        expanded_titles = {}

    current_overall_titles = {}
    past_overall_titles = {}
    final_filters = {}

    # FOR original_title_event in ["CURRENT", "OR", "AND"]
    if original_titles_event in ["CURRENT", "OR", "AND"]:
        for key in expanded_titles.get("current", []):
            current_overall_titles[key] = {
                "type": "CURRENT",
                "min": current_min_value,
                "max": current_max_value,
            }

    # FOR original_title_event in ["PAST", "OR", "AND"]
    if original_titles_event in ["PAST", "OR", "AND"]:
        for key in expanded_titles.get("past", []):
            past_overall_titles[key] = {
                "type": "PAST",
                "min": past_min_value,
                "max": past_max_value,
            }

    for key, value in current_overall_titles.items():
        final_filters[key] = value

    for key, value in past_overall_titles.items():
        if key in final_filters:
            final_filters[key] = {
                "type": "BOTH",
                "min": past_min_value,
                "max": past_max_value,
            }
        else:
            final_filters[key] = value

    returning_filters_keys = final_filters.keys()

    added_titles = list(returning_filters_keys - original_titles_keys)

    added_current_titles = []
    added_past_titles = []
    added_both_titles = []

    for key, value in final_filters.items():
        if key not in original_titles_keys:
            if value.get("type") == "CURRENT":
                added_current_titles.append(key)
            elif value.get("type") == "PAST":
                added_past_titles.append(key)
            elif value.get("type") == "BOTH":
                added_both_titles.append(key)

    modification = {
        "list_of_titles_added_in_current_timeline": added_current_titles,
        "list_of_titles_added_in_past_timeline": added_past_titles,
        "list_of_titles_added_in_both_timelines": added_both_titles,
    }

    industry_filters = {"event": original_titles_event, "filter": final_filters}

    return modification, industry_filters
