import asyncio, json, time, re, sys, os, copy, traceback

from app.utils.qlu2_features.aisearch.utilities.helper_functions.fs_side_functions import (
    map_locations_by_name,
)
from app.utils.qlu2_features.aisearch.utilities.helper_functions.postgres_functions import (
    insert_into_cache_single_entity_results,
)
from app.utils.qlu2_features.aisearch.utilities.helper_functions.misc_functions import (
    extract_generic,
)

from app.utils.qlu2_features.aisearch.suggestions.suggestions_agents import (
    industry_timeline_decider_agent,
    comp_stream_blocked_flag_agent,
    company_multiple_stream_prompts_agent,
)
from qutils.llm.agents.industry import breakdown
import random


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


async def expand_management_titles(all_filters):

    if not all_filters.get("management_level", None):
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

    event = all_filters.get("management_level", {}).get("event", "")
    filters = all_filters.get("management_level", {}).get("filter", {})

    management_levels_to_keep_unchanged = {}
    management_levels_to_expand = {}
    for key, value in filters.items():
        if key not in management_levels:
            management_levels_to_keep_unchanged[key] = filters[key]
        else:
            management_levels_to_expand[key] = filters[key]

    filters = management_levels_to_expand

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

    merged_titles = {**management_levels_to_keep_unchanged}

    management_levels = {"event": event, "filter": merged_titles}

    return management_levels


async def get_filters_compstream_new_companies(
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

    modifications_to_return = {}
    if current_industry_items:
        modifications_to_return["list_of_industries_added_in_current_timeline"] = (
            current_industry_items
        )
    if past_industry_items:
        modifications_to_return["list_of_industries_added_in_past_timeline"] = (
            past_industry_items
        )
    if both_industry_items:
        modifications_to_return["list_of_industries_added_in_both_timelines"] = (
            both_industry_items
        )

    industries_to_return = {"event": default_company_event, "filter": industry_filter}

    return industries_to_return, modifications_to_return


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


def name_search_suggestions():
    suggestions = [
        "Would you like to view a quick summary of ",
        "Want to explore the complete work history of ",
        "Would you like to see the educational background of ",
        "Should we fetch you the contact details of ",
        "Would you like to see the salary trends and pay progression of ",
        "Looking for professionals similar to ",
        "Interested in the core skills and expertise of ",
        "Interested in the industries associated with ",
        "Would you like to review the full professional experience of ",
    ]
    return random.choice(suggestions)


def default_precision_suggestions():
    suggestions = [
        "Let me know how I can refine your search to better match what you're looking for.",
        "Need me to adjust the search? Just let me know what you'd like to focus on or change.",
        "Let me know if there's another way you'd like me to refine your search.",
        "Let me know if there's anything else I can help you with.",
    ]
    return random.choice(suggestions)


def default_strict_match_suggestion():
    suggestions = [
        "Want to make your search more precise? Use exact title matching to narrow down your results."
    ]
    return random.choice(suggestions)


def default_current_timeline_suggestion(modifications):
    company_suggestions = [
        "Would you like to focus only on candidates who currently hold your target roles at your ideal companies?"
    ]
    industry_suggestions = [
        "Would you like to focus only on candidates who currently hold your target roles in your ideal industries?"
    ]
    company_industry_suggestions = [
        "Would you like to focus only on candidates who currently hold your target roles at your ideal companies or industries?"
    ]

    if not modifications:
        return random.choice(company_suggestions)

    if "Company" in modifications and "Industry" not in modifications:
        return random.choice(company_suggestions)
    elif "Company" in modifications and "Industry" in modifications:
        return random.choice(company_industry_suggestions)
    elif "Industry" in modifications and "Company" not in modifications:
        return random.choice(industry_suggestions)
    else:
        return random.choice(company_suggestions)


def no_filter_results_suggestions():
    """
    Returns a random message when a search using filter keywords (job title,
    skills, location, etc.) yields no results, focusing on providing
    clear diagnoses and multiple solutions.
    """
    suggestions = [
        "Let me know how I can refine your search to better match what you're looking for.",
        "Need me to adjust the search? Just let me know what you'd like to focus on or change.",
        "Let me know if there's another way you'd like me to refine your search.",
        "Let me know if there's anything else I can help you with.",
    ]
    return random.choice(suggestions)


def default_company_stream_suggestion():
    suggestions = [
        "Want us to explore multiple company strategies to give you smarter and broader results?"
    ]
    return random.choice(suggestions)


def analyzing_filters_help(filters, count):
    analyzations = []

    if count > 300:
        analyzations.append(
            "The goal for this search would be narrow the results to be less than 300"
        )
    elif count < 100:
        analyzations.append(
            "The goal for this search would be would be to increase the results above 100"
        )
    # elif abs(count - 100) >= abs(count - 300): # closer to 300
    #     analyzations.append("The recall is acceptable. Suggestions goal would, however, be to make the recall closer to a 100")
    elif count > 140:
        analyzations.append(
            "The recall is acceptable but the suggestions goal would be to make the recall closer to a 100 ideally"
        )

    if filters.get("companies") and filters.get("industry"):
        analyzations.append(
            "As company filter and industry filter, both are applied, adding industries would NOT increase recall."
        )

    if filters.get("industry"):
        analyzations.append("No need to add more industries.")

    or_relations_count = 0
    or_relations = "Changing all following filters: "
    for attribute in ["title", "management_level", "companies", "industry"]:
        if filters.get(attribute, {}).get("event", "").lower() != "or":
            if or_relations_count:
                or_relations += ", "

            or_relations += f"{attribute}"
            or_relations_count += 1

    if or_relations_count > 1:
        or_relations += " to OR together would guarantee an increase in recall if and ONLY if ALL these mentioned filters turn to OR; so if increasing results you must suggest turning all these into OR otherwise might not work."
    elif or_relations_count == 1:
        or_relations += " to OR event would increase the results"
    else:
        or_relations = ""

    if count < 100 and or_relations:
        analyzations.append(or_relations)

    analyzations.append(
        "Ensure your suggestion doesn't complete nullify what the user is asking for."
    )

    analyzations_string = ""
    if analyzations:
        analyzations_string = (
            "Key Points you must remember for this set of filters:\n"
            + "\n".join(analyzations)
            + "\n"
        )

    return analyzations_string


async def suggestions_preparations(
    query,
    convId,
    promptId,
    es_client,
    already_given_suggestions=[],
    demoBlocked=False,
    context=None,
):
    if context:
        main_context = context
    else:
        main_context = query

    task_industry_expansion = asyncio.create_task(
        breakdown(query=main_context, num_industries=5, complexity="complex")
    )

    industry_result = await task_industry_expansion

    expansion_results = {
        "industry_keywords": industry_result,
        "original_context": main_context,
        "already_given_suggestions": already_given_suggestions,
    }

    asyncio.create_task(
        insert_into_cache_single_entity_results(
            convId,
            promptId,
            -1,
            "Suggested_Query",
            expansion_results,
            temp=True,
        )
    )
