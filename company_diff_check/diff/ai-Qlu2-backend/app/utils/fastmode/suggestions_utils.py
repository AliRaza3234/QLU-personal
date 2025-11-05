import asyncio, json, time, re, sys, os, copy, traceback
from app.utils.fastmode.prompts import (
    MERGED_EXPANSION_SYSTEM,
    MERGED_EXPANSION_USER,
    SUGGESTIONS_AGENT_SYSTEM,
    SUGGESTIONS_AGENT_USER,
    L2_INDUSTRY_EXPERT_SYSTEM,
    L2_INDUSTRY_EXPERT_USER,
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
from qutils.openrouter.router import llm_async
from app.utils.fastmode.fs_side_functions import map_locations_by_name
from app.utils.fastmode.postgres_functions import (
    insert_into_cache_single_entity_results,
)
from app.utils.fastmode.helper_functions import extract_generic


async def expand_locations(filters1, filters2):
    """
    Merge locations from two filter dictionaries.

    Args:
        filters1: First filter dictionary containing locations
        filters2: Second filter dictionary containing locations

    Returns:
        Dictionary with merged locations from both filters
    """
    filters_1_location = filters1.get("location", None)
    filters_2_location = filters2.get("location", None)

    if filters_1_location and filters_2_location:
        # locations1 = map_locations_by_name(filters_1_location.get("filter", {}))
        location_event = filters1.get("location", {}).get("event", "")

        locations_all = list(filters_2_location.get("filter", {}).keys())
        locations2_mapped = await map_locations_by_name(locations_all)

        if not locations2_mapped:
            return None

        locations2 = {}

        for key, value in locations2_mapped.items():
            locations2[value.get("name", "")] = {
                "urn": value.get("urn", ""),
                "id": value.get("id", ""),
                "type": filters_2_location.get("filter", {})
                .get(key, {})
                .get("type", ""),
            }

        event = (
            filters_1_location.get("event", "")
            if filters_1_location.get("event", "")
            else filters_2_location.get("event", "")
        )
        locations1 = filters_1_location.get("filter", {})
        # locations2 = filters_2_location.get("filter", {})

        merged_current_locations = {}
        merged_previous_locations = {}

        final_filters = {}

        for location, value in locations1.items():
            if value.get("type", "") == "CURRENT":
                merged_current_locations[location] = value.copy()
            elif value.get("type", "") == "PAST":
                merged_previous_locations[location] = value.copy()
            elif value.get("type", "") == "BOTH":
                final_filters[location] = value.copy()

        for location, value in locations2.items():
            if value.get("type", "") == "CURRENT":
                merged_current_locations[location] = value.copy()
            elif value.get("type", "") == "PAST":
                merged_previous_locations[location] = value.copy()
            elif value.get("type", "") == "BOTH":
                final_filters[location] = value.copy()

        for location, value in merged_current_locations.items():
            if location in final_filters:
                final_filters[location]["type"] = "BOTH"
            else:
                final_filters[location] = value.copy()
                final_filters[location]["type"] = "CURRENT"

        for location, value in merged_previous_locations.items():
            if location in final_filters:
                final_filters[location]["type"] = "BOTH"
            else:
                final_filters[location] = value.copy()
                final_filters[location]["type"] = "PAST"

        locations = {"event": event, "filter": final_filters}

        return locations
    else:
        return None


async def expand_titles(filters1, filters2):
    """
    Merge titles from two filter dictionaries.

    Args:
        filters1: First filter dictionary containing titles
        filters2: Second filter dictionary containing titles
    """

    if not filters1.get("title", {}) or not filters2.get("title", {}):
        return None
    else:

        MAX_VALUE = 500000000000
        MIN_VALUE = -1

        current_min_value = MAX_VALUE
        current_max_value = MIN_VALUE
        past_min_value = MAX_VALUE
        past_max_value = MIN_VALUE

        event = (
            filters1.get("title", {}).get("event", "")
            if filters1.get("title", {}).get("event", "")
            else filters2.get("title", {}).get("event", "")
        )

        filters_1 = filters1.get("title", {}).get("filter", {})
        filters_2 = filters2.get("title", {}).get("filter", {})

        for title, value in filters_1.items():
            if value.get("type", "") == "CURRENT":
                current_min_value = min(
                    current_min_value, int(value.get("min", MAX_VALUE))
                )
                current_max_value = max(
                    current_max_value, int(value.get("max", MIN_VALUE))
                )
            elif value.get("type", "") == "PAST":
                past_min_value = min(past_min_value, int(value.get("min", MAX_VALUE)))
                past_max_value = max(past_max_value, int(value.get("max", MIN_VALUE)))

        if current_min_value == MAX_VALUE and current_max_value == MIN_VALUE:
            current_min_value = past_min_value
            current_max_value = past_max_value
        elif past_min_value == MAX_VALUE and past_max_value == MIN_VALUE:
            past_min_value = current_min_value
            past_max_value = current_max_value

        final_filters = {}
        merged_current_titles = {}
        merged_previous_titles = {}

        for title, value in filters_1.items():
            if value.get("type", "") == "CURRENT":
                merged_current_titles[title] = value.copy()
            elif value.get("type", "") == "PAST":
                merged_previous_titles[title] = value.copy()
            elif value.get("type", "") == "BOTH":
                final_filters[title] = value.copy()

        for title, value in filters_2.items():
            if value.get("type", "") == "CURRENT":
                if title not in merged_current_titles:
                    value_copy = value.copy()
                    value_copy["min"] = current_min_value
                    value_copy["max"] = current_max_value
                    merged_current_titles[title] = value_copy
            elif value.get("type", "") == "PAST":
                if title not in merged_previous_titles:
                    value_copy = value.copy()
                    value_copy["min"] = past_min_value
                    value_copy["max"] = past_max_value
                    merged_previous_titles[title] = value_copy
            elif value.get("type", "") == "BOTH":
                if title not in final_filters:
                    value_copy = value.copy()
                    value_copy["min"] = past_min_value
                    value_copy["max"] = past_max_value
                    final_filters[title] = value_copy

        for title, value in merged_current_titles.items():
            if title in final_filters:
                final_filters[title]["type"] = "BOTH"
            else:
                final_filters[title] = value.copy()
                final_filters[title]["type"] = "CURRENT"

        for title, value in merged_previous_titles.items():
            if title in final_filters:
                final_filters[title]["type"] = "BOTH"
            else:
                final_filters[title] = value.copy()
                final_filters[title]["type"] = "PAST"

        titles = {"event": event, "filter": final_filters}

        return titles


async def expand_management_titles(filters):

    if not filters.get("management_level", None):
        return None

    management_levels = [
        "Board of Directors",
        "President",
        "C Suite",
        "Executive and Sr. VP",
        "VP",
        "Director",
        "Head",
        "Manager",
    ]

    event = filters.get("management_level", {}).get("event", "")
    filters = filters.get("management_level", {}).get("filter", {})

    current_management_titles = {}
    previous_management_titles = {}
    both_management_titles = {}

    expanded_current_management_titles = {}
    expanded_previous_management_titles = {}
    expanded_both_management_titles = {}

    for level, value in filters.items():
        if value.get("type", "") == "CURRENT":
            current_management_titles[level] = value
        elif value.get("type", "") == "PAST":
            previous_management_titles[level] = value
        elif value.get("type", "") == "BOTH":
            both_management_titles[level] = value

    if event in ["CURRENT", "OR", "AND"]:
        for level, value in current_management_titles.items():
            if level not in management_levels:
                continue

            index = management_levels.index(level)
            level_below = management_levels[index - 1] if index > 0 else None
            level_above = (
                management_levels[index + 1]
                if index < len(management_levels) - 1
                else None
            )
            expanded_current_management_titles[level] = value.copy()
            if level_below:
                expanded_current_management_titles[level_below] = value.copy()
            if level_above:
                expanded_current_management_titles[level_above] = value.copy()

    if event in ["PAST", "AND"]:
        for level, value in previous_management_titles.items():
            if level not in management_levels:
                continue

            index = management_levels.index(level)
            level_below = management_levels[index - 1] if index > 0 else None
            level_above = (
                management_levels[index + 1]
                if index < len(management_levels) - 1
                else None
            )
            expanded_previous_management_titles[level] = value.copy()
            if level_below:
                expanded_previous_management_titles[level_below] = value.copy()
            if level_above:
                expanded_previous_management_titles[level_above] = value.copy()

    if event in ["CURRENT", "OR"]:
        for level, value in both_management_titles.items():
            if level not in management_levels:
                continue
            index = management_levels.index(level)
            level_below = management_levels[index - 1] if index > 0 else None
            level_above = (
                management_levels[index + 1]
                if index < len(management_levels) - 1
                else None
            )
            if level not in expanded_current_management_titles:
                expanded_current_management_titles[level] = {"type": "CURRENT"}
            if level_below:
                if level_below not in expanded_current_management_titles:
                    expanded_current_management_titles[level_below] = {
                        "type": "CURRENT"
                    }
            if level_above:
                if level_above not in expanded_current_management_titles:
                    expanded_current_management_titles[level_above] = {
                        "type": "CURRENT"
                    }

    elif event == "PAST":
        for level, value in both_management_titles.items():
            if level not in management_levels:
                continue
            index = management_levels.index(level)
            level_below = management_levels[index - 1] if index > 0 else None
            level_above = (
                management_levels[index + 1]
                if index < len(management_levels) - 1
                else None
            )
            if level not in expanded_previous_management_titles:
                expanded_previous_management_titles[level] = {
                    "type": "PAST",
                }
            if level_below:
                if level_below not in expanded_previous_management_titles:
                    expanded_previous_management_titles[level_below] = {"type": "PAST"}
            if level_above:
                if level_above not in expanded_previous_management_titles:
                    expanded_previous_management_titles[level_above] = {"type": "PAST"}

    elif event == "AND":
        for level, value in both_management_titles.items():
            if level not in management_levels:
                continue
            index = management_levels.index(level)
            level_below = management_levels[index - 1] if index > 0 else None
            level_above = (
                management_levels[index + 1]
                if index < len(management_levels) - 1
                else None
            )
            if level not in expanded_both_management_titles:
                expanded_both_management_titles[level] = value.copy()
            if level_below:
                if level_below not in expanded_both_management_titles:
                    expanded_both_management_titles[level_below] = value.copy()
            if level_above:
                if level_above not in expanded_both_management_titles:
                    expanded_both_management_titles[level_above] = value.copy()

    merged_titles = {**expanded_current_management_titles}
    for level, value in expanded_previous_management_titles.items():
        if level in merged_titles:
            merged_titles[level]["type"] = "BOTH"
        else:
            merged_titles[level] = value

    for level, value in expanded_both_management_titles.items():
        if level in merged_titles:
            merged_titles[level]["type"] = "BOTH"
        else:
            merged_titles[level] = value.copy()

    management_levels = {"event": event, "filter": merged_titles}

    return management_levels


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

    response = await llm_async(
        messages=messages,
        model="meta-llama/llama-3.3-70b-instruct",
        extra_body={"provider": {"order": ["groq", "cerebras"]}},
        temperature=1,
    )

    expanded_query = extract_generic("<expanded_query>", "</expanded_query>", response)

    return expanded_query


async def run_l2_industry_expert(conversation_context):

    if not conversation_context:
        return None

    messages = [
        {"role": "system", "content": L2_INDUSTRY_EXPERT_SYSTEM},
        {
            "role": "user",
            "content": (L2_INDUSTRY_EXPERT_USER).replace(
                "{{conversation_context}}", str(conversation_context)
            ),
        },
    ]

    response = await llm_async(
        messages=messages,
        model="openai/gpt-4.1-mini",
        extra_body={"provider": {"order": ["openai"]}},
        temperature=0.1,
    )

    filters = extract_generic("<filters_json>", "</filters_json>", response)

    return filters


async def generate_suggestions_agent(
    priority_instructions,
    conversation_context,
    priority_order_list=[],
    flag_definitions="",
):

    suggestions_filters = {}
    suggestions_text = ""

    messages = [
        {"role": "system", "content": SUGGESTIONS_AGENT_SYSTEM},
        {
            "role": "user",
            "content": (SUGGESTIONS_AGENT_USER)
            .replace("{{prioritized_instructions}}", str(priority_instructions))
            .replace("{{conversation_context}}", str(conversation_context))
            .replace("{{flag_definitions}}", str(flag_definitions)),
        },
    ]

    response = await llm_async(
        messages=messages,
        model="openai/gpt-4.1",
        extra_body={"provider": {"order": ["openai"]}},
        temperature=0.1,
    )

    suggestions_filters_index = extract_generic(
        "<selected_order_of_priority>", "</selected_order_of_priority>", response
    )
    if suggestions_filters_index:
        suggestions_filters_index = int(suggestions_filters_index.strip("")) - 1
    else:
        suggestions_filters_index = 100

    selected_suggestions_key = "filters_1"
    if priority_order_list and isinstance(suggestions_filters_index, int):
        if suggestions_filters_index < len(priority_order_list):
            selected_suggestions_key = priority_order_list[suggestions_filters_index]
        else:
            selected_suggestions_key = "filters_1"

    suggestions_text = extract_generic(
        "<suggestions_message>", "</suggestions_message>", response
    )

    return selected_suggestions_key, suggestions_text, response


async def filters_compstream_new_companies_agent(
    l0_filters,
    convId,
    promptId,
    prompt,
    current_task,
    current_blocked,
    past_task,
    past_blocked,
):
    timeline = l0_filters.get("companies", {}).get("event", "")
    current_company_prompts_variants = []
    past_company_prompts_variants = []
    if not current_blocked:
        current_company_prompts_variants = await current_task if current_task else []
    if not past_blocked:
        past_company_prompts_variants = await past_task if past_task else []

    filters_compstream = copy.deepcopy(l0_filters)

    if timeline == "PAST":
        past_company_prompts_variants = current_company_prompts_variants
        current_company_prompts_variants = []

    filters_compstream.update(
        {
            "new_companies": {
                "current": current_company_prompts_variants,
                "past": past_company_prompts_variants,
                "timeline": timeline,
            }
        }
    )

    asyncio.create_task(
        insert_into_cache_single_entity_results(
            conversation_id=convId,
            prompt_id=promptId,
            response_id=-15,
            prompt=prompt,
            result={"selected_filters": filters_compstream},
            temp=True,
        )
    )

    return {"selected_filters": filters_compstream}


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

    response = await llm_async(
        messages=messages,
        model="anthropic/claude-sonnet-4",
        extra_body={
            "provider": {"order": ["anthropic", "google-vertex", "amazon-bedrock"]}
        },
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


def transform_industry_filters(filters, company_event):
    """
    {
        "current" : {"included" : ["mobile telecommunications", "wireless services", "cellular networks", "mobile operators", "wireless carriers", "mobile broadband", "wireless communications", "mobile data", "cellular services", "wireless connectivity", "mobile networks", "wireless infrastructure"], "excluded" : []},
        "past" : {"included" : [], "excluded" : []},
        "both" : {"included" : [], "excluded" : []},
        "event" : "CURRENT"
    }
    """

    if not filters:
        return None

    industry_filters = filters.get("industry", {})

    current_filters = {}
    current_filters_excluded = {}
    past_filters = {}
    past_filters_excluded = {}
    both_filters = {}
    both_filters_excluded = {}

    # ADDING CURRENT FILTERS AND PAST FILTERS TO APPROPRIATE DICTS
    if company_event in ["CURRENT", "OR", "AND"]:
        for item in industry_filters.get("current", {}).get("included", []):
            current_filters[item] = {
                "type": "CURRENT",
                "exclusion": False,
            }
        for item in industry_filters.get("current", {}).get("excluded", []):
            current_filters_excluded[item] = {
                "type": "CURRENT",
                "exclusion": True,
            }
    if company_event in ["PAST", "AND"]:
        for item in industry_filters.get("past", {}).get("included", []):
            past_filters[item] = {
                "type": "PAST",
                "exclusion": False,
            }
        for item in industry_filters.get("past", {}).get("excluded", []):
            past_filters_excluded[item] = {
                "type": "PAST",
                "exclusion": True,
            }

    # IF ELSE TO TRANSFORM BOTH FILTERS TO CURRENT OR PAST DEPENDING ON THE COMPANY EVENT
    if company_event == "PAST":
        for item in industry_filters.get("both", {}).get("included", []):
            past_filters[item] = {
                "type": "PAST",
                "exclusion": False,
            }
        for item in industry_filters.get("both", {}).get("excluded", []):
            past_filters_excluded[item] = {
                "type": "PAST",
                "exclusion": True,
            }
    elif company_event == "CURRENT":
        for item in industry_filters.get("both", {}).get("included", []):
            current_filters[item] = {
                "type": "CURRENT",
                "exclusion": False,
            }
        for item in industry_filters.get("both", {}).get("excluded", []):
            current_filters_excluded[item] = {
                "type": "CURRENT",
                "exclusion": True,
            }

    elif company_event in ["AND"]:
        for item in industry_filters.get("both", {}).get("included", []):
            both_filters[item] = {
                "type": "BOTH",
                "exclusion": False,
            }
        for item in industry_filters.get("both", {}).get("excluded", []):
            both_filters_excluded[item] = {
                "type": "BOTH",
                "exclusion": True,
            }
    elif company_event in ["OR"]:
        for item in industry_filters.get("both", {}).get("included", []):
            current_filters[item] = {
                "type": "CURRENT",
                "exclusion": False,
            }
        for item in industry_filters.get("both", {}).get("excluded", []):
            current_filters_excluded[item] = {
                "type": "CURRENT",
                "exclusion": True,
            }

    final_filters = {}
    # Non EXCLUDED FILTERS
    for key, value in current_filters.items():
        final_filters[key] = value

    for key, value in past_filters.items():
        if key in current_filters:
            final_filters[key] = {
                "type": "BOTH",
                "exclusion": False,
            }
        else:
            final_filters[key] = value
    for key, value in both_filters.items():
        if key in current_filters:
            final_filters[key] = {
                "type": "BOTH",
                "exclusion": False,
            }
        else:
            final_filters[key] = value

    # FOR EXCLUDED FILTERS
    for key, value in current_filters_excluded.items():
        if key in final_filters:
            final_filters[key] = {
                "type": "BOTH",
                "exclusion": True,
            }
        else:
            final_filters[key] = value

    for key, value in past_filters_excluded.items():
        if key in final_filters:
            final_filters[key] = {
                "type": "BOTH",
                "exclusion": True,
            }
        else:
            final_filters[key] = value

    for key, value in both_filters_excluded.items():
        if key in final_filters:
            final_filters[key] = {
                "type": "BOTH",
                "exclusion": True,
            }
        else:
            final_filters[key] = value

    return final_filters


async def titles_expansion_suggestions(titles, context):

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
    response = await llm_async(
        messages=messages,
        model="openai/gpt-4.1",
        extra_body={"provider": {"order": ["openai"]}},
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


def structure_titles_for_suggestions(titles_dict, event, minn, maxx):
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

    response = await llm_async(
        messages=messages,
        model="openai/gpt-4.1-mini",
        extra_body={"provider": {"order": ["openai"]}},
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


async def transform_timeline_for_precision(filters):
    l0_filters = copy.deepcopy(filters)
    titles = l0_filters.get("title", {})
    company = l0_filters.get("companies", {})
    industry = l0_filters.get("industry", {})

    titles_event = titles.get("event", None)
    company_event = company.get("event", None)
    industry_event = industry.get("event", None)

    selected_event = None
    modifications = []

    # Title only
    if titles_event and not company_event and not industry_event:
        if titles_event == "OR":
            selected_event = "CURRENT"
    elif company_event and not titles_event and not industry_event:
        if company_event == "OR":
            selected_event = "CURRENT"
    elif industry_event and not titles_event and not company_event:
        if industry_event == "OR":
            selected_event = "CURRENT"
    elif titles_event and company_event and not industry_event:
        if titles_event == company_event == "OR":
            selected_event = "CURRENT"
        elif titles_event == "CURRENT" and company_event == "OR":
            selected_event = "CURRENT"
        elif titles_event == "PAST" and company_event == "OR":
            selected_event = "PAST"
        elif company_event == "CURRENT" and titles_event == "OR":
            selected_event = "CURRENT"
        elif company_event == "PAST" and titles_event == "OR":
            selected_event = "PAST"
    elif titles_event and industry_event and not company_event:
        if titles_event == industry_event == "OR":
            selected_event = "CURRENT"
        elif titles_event == "CURRENT" and industry_event == "OR":
            selected_event = "CURRENT"
        elif titles_event == "PAST" and industry_event == "OR":
            selected_event = "PAST"
        elif industry_event == "CURRENT" and titles_event == "OR":
            selected_event = "CURRENT"
        elif industry_event == "PAST" and titles_event == "OR":
            selected_event = "PAST"
    elif titles_event and company_event and industry_event:
        if titles_event == company_event == industry_event == "OR":
            selected_event = "CURRENT"
        elif (
            titles_event == "CURRENT"
            and company_event in ["OR", "CURRENT"]
            and industry_event in ["CURRENT", "OR"]
        ):
            selected_event = "CURRENT"
        elif (
            titles_event == "PAST"
            and company_event in ["OR", "PAST"]
            and industry_event in ["PAST", "OR"]
        ):
            selected_event = "PAST"
        elif (
            company_event == "CURRENT"
            and titles_event in ["OR", "CURRENT"]
            and industry_event in ["CURRENT", "OR"]
        ):
            selected_event = "CURRENT"
        elif (
            company_event == "PAST"
            and titles_event in ["OR", "PAST"]
            and industry_event in ["PAST", "OR"]
        ):
            selected_event = "PAST"
        elif (
            industry_event == "CURRENT"
            and titles_event in ["OR", "CURRENT"]
            and company_event in ["CURRENT", "OR"]
        ):
            selected_event = "CURRENT"
        elif (
            industry_event == "PAST"
            and titles_event in ["OR", "PAST"]
            and company_event in ["PAST", "OR"]
        ):
            selected_event = "PAST"
    else:
        return None, None

    # Modifications:
    if filters.get("title", {}).get("event") == "OR":
        modifications.append("Job Title")
    if filters.get("companies", {}).get("event") == "OR":
        modifications.append("Company")
    if filters.get("industry", {}).get("event") == "OR":
        modifications.append("Industry")

    if selected_event:
        if l0_filters.get("title"):
            l0_filters.get("title", {})["event"] = selected_event
        if l0_filters.get("companies"):
            l0_filters.get("companies", {})["event"] = selected_event
        if l0_filters.get("industry"):
            l0_filters.get("industry", {})["event"] = selected_event
        return l0_filters, modifications

    return None, None


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

    response = await llm_async(
        messages=messages,
        model="openai/gpt-4.1-mini",
        extra_body={"provider": {"order": ["openai"]}},
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

    response = await llm_async(
        messages=messages,
        model="openai/gpt-4.1",
        extra_body={"provider": {"order": ["openai"]}},
        temperature=1,
    )

    industry_json = extract_generic("<industry_json>", "</industry_json>", response)

    try:
        response_data = json.loads(industry_json)
    except (json.JSONDecodeError, ValueError, TypeError):
        response_data = {}

    return {"industry": response_data}


async def get_industries_with_timelines_and_modifications(
    industry_keywords_input, l0_filters
):

    industry_keywords = []

    for key, value in industry_keywords_input.items():
        for item in value:
            industry_keywords.append(item)

    industries_to_return = None
    modifications_to_return = None

    default_company_event = l0_filters.get("companies", {}).get("event", None)

    industry_filter = {}

    shorten_current_prompts_list = []
    shorten_past_prompts_list = []

    for item in l0_filters.get("companies", {}).get("current", []):
        if item.get("prompt"):
            shorten_current_prompts_list.append(item.get("prompt"))
    for item in l0_filters.get("companies", {}).get("past", []):
        if item.get("prompt"):
            shorten_past_prompts_list.append(item.get("prompt"))

    # if default_company_event == "OR":
    #     for key in industry_keywords:
    #         industry_filter[key] = {
    #             "type": "CURRENT",
    #             "exclusion": False,
    #         }

    # elif default_company_event == "CURRENT":
    #     for key in industry_keywords:
    #         industry_filter[key] = {
    #             "type": "CURRENT",
    #             "exclusion": False,
    #         }
    # elif default_company_event == "PAST":
    #     for key in industry_keywords:
    #         industry_filter[key] = {
    #             "type": "PAST",
    #             "exclusion": False,
    #         }
    # elif default_company_event == "AND":
    # call the llm to get the industries in appropriate timeline
    industry_filter_temp = await industry_timeline_decider_agent(
        industry_keywords_input,
        shorten_current_prompts_list,
        shorten_past_prompts_list,
    )
    industry_filter = transform_industry_filters(
        industry_filter_temp, default_company_event
    )

    current_industry_items = []
    past_industry_items = []
    both_industry_items = []

    for key, value in industry_filter.items():
        if value.get("type") == "CURRENT":
            current_industry_items.append(key)
        elif value.get("type") == "PAST":
            past_industry_items.append(key)
        elif value.get("type") == "BOTH":
            both_industry_items.append(key)

    modifications_to_return = {
        "list_of_industries_added_in_current_timeline": current_industry_items,
        "list_of_industries_added_in_past_timeline": past_industry_items,
        "list_of_industries_added_in_both_timelines": both_industry_items,
    }

    industries_to_return = {"event": default_company_event, "filter": industry_filter}

    return industries_to_return, modifications_to_return


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

    response = await llm_async(
        messages=messages,
        model="openai/gpt-4.1",
        extra_body={"provider": {"order": ["openai"]}},
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

    response = await llm_async(
        messages=messages,
        model="openai/gpt-4.1",
        extra_body={"provider": {"order": ["openai"]}},
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

    response = await llm_async(
        messages=messages,
        model="openai/gpt-4.1",
        extra_body={"provider": {"order": ["openai"]}},
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

    response = await llm_async(
        messages=messages,
        model="openai/gpt-4.1",
        extra_body={"provider": {"order": ["openai"]}},
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

    response = await llm_async(
        messages=messages,
        model="openai/gpt-4.1",
        extra_body={"provider": {"order": ["openai"]}},
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

    response = await llm_async(
        messages=messages,
        model="meta-llama/llama-3.3-70b-instruct",
        extra_body={"provider": {"order": ["groq", "cerebras"]}},
        temperature=0.6,
    )

    return response


def transform_min_max(input_dict, l0_default_filters):
    min_max_dict = copy.deepcopy(input_dict)
    if min_max_dict.get("min", None) and l0_default_filters.get("min", None):
        if min_max_dict.get("min") > l0_default_filters.get("min"):
            min_max_dict["min"] = l0_default_filters.get("min") - 1
    if min_max_dict.get("max", None) and l0_default_filters.get("max", None):
        if min_max_dict.get("max") < l0_default_filters.get("max"):
            min_max_dict["max"] = l0_default_filters.get("max") + 1
    return min_max_dict


def get_atomic_filters(filters):

    def transformed_min_max(filters):
        min = filters.get("min")
        max = filters.get("max")

        min_difference_value = 2 if min <= 10 else 5
        max_difference_value = 2 if max <= 10 else 5

        new_min = min - min_difference_value
        new_max = max + max_difference_value

        if new_min < 0:
            new_min = 0
        if new_max > 60:
            new_max = 60

        modified = False
        if new_min != min or new_max != max:
            modified = True

        return {"min": new_min, "max": new_max}, modified

    experience = filters.get("experience", {})
    role_tenure = filters.get("role_tenure", {})
    company_tenure = filters.get("company_tenure", {})
    modifications = []

    modifications_string = ""

    if experience.get("min", None):
        experience, modified_experience = transformed_min_max(experience)
        if modified_experience:
            modifications.append("Experience")
            modifications_string += f"Experience: (Number of Years) {experience} \n"
    if role_tenure.get("min", None):
        role_tenure, modified_role_tenure = transformed_min_max(role_tenure)
        if modified_role_tenure:
            modifications.append("Role Tenure")
            modifications_string += f"Role Tenure: (Number of Years){role_tenure} \n"
    if company_tenure.get("min", None):
        company_tenure, modified_company_tenure = transformed_min_max(company_tenure)
        if modified_company_tenure:
            modifications.append("Company Tenure")
            modifications_string += (
                f"Company Tenure:(Number of Years) {company_tenure} \n"
            )

    filters.update(
        {
            "experience": experience,
            "role_tenure": role_tenure,
            "company_tenure": company_tenure,
        }
    )

    if not experience and not role_tenure and not company_tenure:
        return None, [], ""
    else:
        return filters, modifications, modifications_string


async def get_new_companies_dict(
    convID, promptID, prompt, shorten_prompt_current, shorten_prompt_past, event
):
    """
    Accepts the following arguments:
    - convID: The conversation ID : str
    - promptID: The prompt ID : int
    - prompt: The prompt : str
    - shorten_prompt_current: The shortened prompt for the current timeline : str
    - shorten_prompt_past: The shortened prompt for the past timeline : str
    - event: The event (current, past, or both) : str
    """

    is_current_blocked_task = None
    is_past_blocked_task = None
    multiple_stream_variants_current_task = None
    multiple_stream_variants_past_task = None

    if shorten_prompt_current:
        is_current_blocked_task = asyncio.create_task(
            comp_stream_blocked_flag_agent(shorten_prompt_current)
        )
        multiple_stream_variants_current_task = asyncio.create_task(
            (
                company_multiple_stream_prompts_agent(
                    company_description_input=shorten_prompt_current,
                    response_id=-102,
                    convId=convID,
                    promptId=promptID,
                    prompt=prompt,
                    mode="not_suggestions",
                )
            )
        )
    if shorten_prompt_past:
        is_past_blocked_task = asyncio.create_task(
            comp_stream_blocked_flag_agent(shorten_prompt_past)
        )
        multiple_stream_variants_past_task = asyncio.create_task(
            (
                company_multiple_stream_prompts_agent(
                    company_description_input=shorten_prompt_past,
                    response_id=-103,
                    convId=convID,
                    promptId=promptID,
                    prompt=prompt,
                    mode="not_suggestions",
                )
            )
        )

    if is_current_blocked_task:
        is_current_blocked, current_response = await is_current_blocked_task
    else:
        is_current_blocked = True
        current_response = None
    if is_past_blocked_task:
        is_past_blocked, past_response = await is_past_blocked_task
    else:
        is_past_blocked = True
        past_response = None

    if (
        shorten_prompt_current
        and (not is_current_blocked)
        and multiple_stream_variants_current_task
    ):
        multiple_stream_variants_current = await multiple_stream_variants_current_task
        if not multiple_stream_variants_current:
            multiple_stream_variants_current.append(shorten_prompt_current)
    else:
        multiple_stream_variants_current = (
            [shorten_prompt_current] if shorten_prompt_current else []
        )

    if (
        shorten_prompt_past
        and (not is_past_blocked)
        and multiple_stream_variants_past_task
    ):
        multiple_stream_variants_past = await multiple_stream_variants_past_task
        if not multiple_stream_variants_past:
            multiple_stream_variants_past.append(shorten_prompt_past)
    else:
        multiple_stream_variants_past = (
            [shorten_prompt_past] if shorten_prompt_past else []
        )

    # For Debugging Purposes

    flags_reasoning = {
        "current_flag": is_current_blocked,
        "past_flag": is_past_blocked,
        "current_response": current_response,
        "past_response": past_response,
        "current_variants": multiple_stream_variants_current,
        "past_variants": multiple_stream_variants_past,
        "timeline": event,
    }

    asyncio.create_task(
        insert_into_cache_single_entity_results(
            conversation_id=convID,
            prompt_id=promptID,
            response_id=-104,
            prompt=prompt,
            result={"flags_reasoning": flags_reasoning},
            temp=True,
        )
    )

    return {
        "current": multiple_stream_variants_current,
        "past": multiple_stream_variants_past,
        "timeline": event,
    }, "companies"
