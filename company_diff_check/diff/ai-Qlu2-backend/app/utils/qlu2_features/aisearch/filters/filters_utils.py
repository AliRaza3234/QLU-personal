import os
import copy
import asyncio

from app.utils.qlu2_features.aisearch.utilities.helper_functions.fs_side_functions import (
    map_locations_by_name,
)
from app.utils.qlu2_features.aisearch.utilities.helper_functions.postgres_functions import (
    insert_into_cache_single_entity_results,
)
from app.utils.qlu2_features.aisearch.utilities.helper_functions.misc_functions import (
    last_converter,
)

from app.utils.qlu2_features.aisearch.filters.filters_prompts import (
    LOCATIONS_VERIFIER_AGENT,
    KEYWORD_WITH_TITLE_PROMPT,
)
from app.utils.qlu2_features.aisearch.suggestions.suggestions_utils import (
    get_new_companies_dict,
)

from app.utils.qlu2_features.aisearch.utilities.llm_functions.llms import grok


async def titles_handling(titles_dict, aisearch_payload):
    return titles_dict, "titles"
    titles_excluded_prefixes = {
        "President": [
            "Vice",
            "Executive",
            "Senior",
            "Associate",
            "Assistant",
            "Deputy",
            "Regional",
            "Area",
            "Divisional",
            "Junior",
            "Group",
            "Interim",
            "Acting",
            "Former",
            "Ex",
            "Emeritus",
            "National",
        ],
        "Vice President": [
            "Executive",
            "Senior",
            "Associate",
            "Assistant",
            "Deputy",
            "Regional",
            "Area",
            "Divisional",
            "Junior",
            "Group",
            "Interim",
            "Acting",
            "Former",
            "Ex",
            "Emeritus",
            "National",
            "Lead",
        ],
        "Director": [
            "Executive",
            "Senior",
            "Junior",
            "Associate",
            "Assistant",
            "Deputy",
            "Regional",
            "Divisional",
            "Group",
            "Managing",
            "Interim",
            "Acting",
            "Lead",
            "Area",
            "National",
            "Former",
            "Ex",
            "Emeritus",
        ],
        "Managing Director": [
            "Deputy",
            "Assistant",
            "Associate",
            "Junior",
            "Interim",
            "Regional",
            "Area",
            "Divisional",
            "Acting",
            "Lead",
            "Former",
            "Ex",
        ],
        "Executive Director": [
            "Deputy",
            "Associate",
            "Assistant",
            "Junior",
            "Interim",
            "Acting",
            "Lead",
            "Former",
            "Ex",
        ],
        "Manager": [
            "Senior",
            "Junior",
            "Assistant",
            "Associate",
            "Deputy",
            "Regional",
            "Area",
            "Divisional",
            "General",
            "Interim",
            "Acting",
            "Group",
            "Lead",
            "Former",
            "Ex",
        ],
        "General Manager": [
            "Deputy",
            "Assistant",
            "Associate",
            "Junior",
            "Regional",
            "Area",
            "Divisional",
            "Interim",
            "Acting",
            "Lead",
            "Group",
            "Former",
            "Ex",
        ],
        "Head": [
            "Deputy",
            "Associate",
            "Assistant",
            "Interim",
            "Acting",
            "Junior",
            "Former",
            "Ex",
            "Group",
            "National",
        ],
        "Partner": [
            "Senior",
            "Managing",
            "Junior",
            "Associate",
            "Executive",
            "Founding",
            "Principal",
            "Regional",
            "Area",
            "Divisional",
            "Lead",
            "Emeritus",
            "Former",
            "Ex",
        ],
    }

    chief_excluded_prefix = [
        "Deputy",
        "Interim",
        "Acting",
        "Assistant",
        "Associate",
        "Incoming",
        "Former",
        "Ex",
        "Designate",
        "Emeritus",
    ]

    if titles_dict:
        titles_acronyms = [
            item
            for item in titles_dict.get("filter")
            if len(item) <= 5
            and not titles_dict.get("filter").get(item, {}).get("keywords", None)
        ]

        keyword_title_dict = {}
        if titles_acronyms:
            keyword_title_message = [
                {"role": "system", "content": KEYWORD_WITH_TITLE_PROMPT},
                {
                    "role": "user",
                    "content": f"""<Prompt>\n{aisearch_payload}\n</Prompt>\n<all_titles>\n{titles_dict.get("filter").keys()}\n</all_titles>\n<extracted_titles>\n{titles_acronyms}\n</extracted_titles>""",
                },
            ]
            try:
                keyword_title_dict = await grok(keyword_title_message)
            except:
                pass

        try:
            for loc in list(titles_dict.get("filter").keys()):
                base_title = None

                for title_key in titles_excluded_prefixes.keys():
                    if title_key in loc:
                        base_title = title_key
                        break

                excluded_list = []
                if loc.startswith("Chief") and base_title is None:
                    excluded_list = chief_excluded_prefix.copy()

                    words_in_title = loc.split()
                    excluded_list = [
                        prefix
                        for prefix in excluded_list
                        if prefix not in words_in_title
                    ]

                elif base_title:
                    excluded_list = titles_excluded_prefixes[base_title].copy()

                    words_in_title = loc.split()
                    excluded_list = [
                        prefix
                        for prefix in excluded_list
                        if prefix not in words_in_title
                    ]

                    titles_dict["filter"][loc]["excluded_keywords"] = excluded_list

                titles_dict["filter"][loc]["excluded_keywords"] = excluded_list
                titles_dict["filter"][loc]["keywords"] = keyword_title_dict.get(loc, [])
        except:
            pass

    return titles_dict, "titles"


async def locations_processing(locations_aisearch, aisearch_payload):
    temp_locations_aisearch = copy.deepcopy(locations_aisearch)
    if locations_aisearch:
        location_all = [
            item
            for item in locations_aisearch.get("filter", {}).keys()
            if "urn" not in locations_aisearch.get("filter", {}).get(item)
        ]

        mapped_locations = await map_locations_by_name(location_all)
        all_locs = []
        new_locations = []
        for key in list(locations_aisearch.get("filter", {})):
            if mapped_locations.get(key):
                new_locations.append(mapped_locations[key]["name"])
                locations_aisearch["filter"][mapped_locations[key]["name"]] = (
                    locations_aisearch["filter"].pop(key)
                )

                locations_aisearch["filter"][mapped_locations[key]["name"]]["id"] = (
                    mapped_locations[key].get("id", None)
                )
                locations_aisearch["filter"][mapped_locations[key]["name"]]["urn"] = (
                    mapped_locations[key].get("urn", None)
                )
            else:
                if "urn" not in locations_aisearch.get("filter", {}).get(key):
                    locations_aisearch["filter"].pop(key)

        if locations_aisearch.get("filter") and new_locations:
            all_locs = list(locations_aisearch.get("filter", {}).keys())
            if all_locs:
                locations_verifier = [
                    {"role": "system", "content": LOCATIONS_VERIFIER_AGENT},
                    {
                        "role": "user",
                        "content": f"""<Prompt>\n{aisearch_payload}\n</Prompt>\n<extracted_locations>\n{all_locs}\n</extracted_locations>\n# **Remember to process ONLY entities in extracted_locations and ensure the output's spelling matches exactly as it appears in this list**""",
                    },
                ]
                try:
                    location_verified = await grok(locations_verifier)
                    for loc in list(locations_aisearch.get("filter").keys()):
                        if loc not in location_verified:
                            locations_aisearch["filter"].pop(loc)
                    locations_aisearch = (
                        locations_aisearch if locations_aisearch.get("filter") else {}
                    )
                except:
                    locations_aisearch = temp_locations_aisearch
                    pass
    return locations_aisearch, "locations"


async def handling_titles_locations(
    titles_location_tasks, temp_filters, count_response
):
    for coro in asyncio.as_completed(titles_location_tasks):
        item = await coro

        if item[1] == "titles":
            titles_dict = item[0]
            if titles_dict:
                temp_filters.update({"title": titles_dict})

            return_payload = {
                "step": "filters",
                "filters_object": temp_filters,
                "response_id": count_response,
            }
            yield last_converter(return_payload)

        if item[1] == "locations":

            locations_aisearch = item[0]
            return_payload = {
                "step": "location_filter",
                "filters_object": {"location": locations_aisearch},
                "response_id": count_response,
            }
            yield last_converter(return_payload)

        if item[1] == "companies":
            company_dict = item[0]
            return_payload = {
                "step": "company_filters",
                "filters_object": company_dict,
                "response_id": count_response,
            }
            yield last_converter(return_payload)


async def new_aisearch_results(
    aisearch_payload, temp_filters, count_response, convId, promptId, main_query
):
    aisearch_results = []
    locations_aisearch = {}
    # for coro in asyncio.as_completed(subtasks):

    # if isinstance(temp_filters, tuple):
    aisearch_results.append(temp_filters)

    locations_aisearch = (
        temp_filters.pop("location") if "location" in temp_filters else {}
    )

    companies_dict = temp_filters.pop("companies", {})
    titles_dict = temp_filters.get("title")

    if titles_dict and titles_dict.get("event"):
        if companies_dict and companies_dict.get("timeline"):
            titles_event = titles_dict.get("event")
            companies_event = companies_dict.get("timeline")
            accepted = ["OR", "CURRENT"]
            if titles_event in accepted and companies_event in accepted:
                companies_event = titles_event
            companies_dict["timeline"] = companies_event

    if companies_dict:
        shorten_prompt_current = (
            companies_dict.get("current")[0] if companies_dict.get("current") else ""
        )
        shorten_prompt_past = (
            companies_dict.get("past")[0] if companies_dict.get("past") else ""
        )
        event = companies_dict.get("timeline")

        count_response += 1
        return_payload = {
            "step": "shorten_prompts",
            "shorten_prompts": {
                "current": shorten_prompt_current,
                "past": shorten_prompt_past,
                "event": event,
            },
            "response_id": count_response,
        }
        yield last_converter(return_payload)
        count_response += 1

        titles_location_companies_tasks = [
            titles_handling(titles_dict, aisearch_payload),
            locations_processing(locations_aisearch, aisearch_payload),
            get_new_companies_dict(
                convId,
                promptId,
                main_query,
                shorten_prompt_current,
                shorten_prompt_past,
                event,
            ),
        ]
    else:
        return_payload = {
            "step": "company_filters",
            "filters_object": companies_dict,
            "response_id": count_response,
        }
        yield last_converter(return_payload)

        titles_location_companies_tasks = [
            titles_handling(titles_dict, aisearch_payload),
            locations_processing(locations_aisearch, aisearch_payload),
        ]

    async for chunk in handling_titles_locations(
        titles_location_companies_tasks, temp_filters, count_response
    ):
        yield chunk

    results = []
    results.append(
        {
            "AI_Search_Results": aisearch_results,
            "clear_prompt": aisearch_payload,
        }
    )
    asyncio.create_task(
        insert_into_cache_single_entity_results(
            convId, promptId, count_response, main_query, results[0]
        )
    )
    return


async def processing_aisearch_results(
    temp_filters,
    count_response,
    aisearch_payload,
    convId,
    promptId,
    special_handling=True,
):

    locations_aisearch = (
        temp_filters.pop("location") if "location" in temp_filters else {}
    )

    companies_filter = {}
    if temp_filters.get("companies", {}):
        if temp_filters.get("companies", {}).get("current", []):
            if isinstance(temp_filters.get("companies", {}).get("current", [])[0], str):
                companies_filter = temp_filters.pop("companies", {})
        elif temp_filters.get("companies", {}).get("past", []):
            if isinstance(temp_filters.get("companies", {}).get("past", [])[0], str):
                companies_filter = temp_filters.pop("companies", {})

        if isinstance(
            temp_filters.get("companies", {}).get("current", []), str
        ) or isinstance(temp_filters.get("companies", {}).get("past", []), str):
            companies_filter = temp_filters.pop("companies", {})
            companies_filter.update(
                {
                    "current": (
                        [companies_filter.get("current", None)]
                        if companies_filter.get("current", "")
                        else []
                    ),
                    "past": (
                        [companies_filter.get("past", None)]
                        if companies_filter.get("past", "")
                        else []
                    ),
                }
            )

    block_companies = False
    if temp_filters.get("new_companies", {}):
        block_companies = True
        if temp_filters.get("new_companies", {}).get("current", []):
            if isinstance(
                temp_filters.get("new_companies", {}).get("current", [])[0], str
            ):
                companies_filter = temp_filters.pop("new_companies", {})
        elif temp_filters.get("new_companies", {}).get("past", []):
            if isinstance(
                temp_filters.get("new_companies", {}).get("past", [])[0], str
            ):
                companies_filter = temp_filters.pop("new_companies", {})

    titles_dict = temp_filters.get("title")

    if titles_dict and titles_dict.get("event"):
        if companies_filter and companies_filter.get("timeline"):
            titles_event = titles_dict.get("event")
            companies_event = companies_filter.get("timeline")
            accepted = ["OR", "CURRENT"]
            if titles_event in accepted and companies_event in accepted:
                companies_event = titles_event
            companies_filter["timeline"] = companies_event

    if (
        companies_filter
        and (
            (
                companies_filter.get("current") is not None
                and len(companies_filter["current"]) == 1
            )
            or (
                companies_filter.get("past") is not None
                and len(companies_filter["past"]) == 1
            )
        )
        and not block_companies
        and special_handling
    ):
        shorten_prompt_current = (
            companies_filter.get("current")[0]
            if companies_filter.get("current")
            else ""
        )
        shorten_prompt_past = (
            companies_filter.get("past")[0] if companies_filter.get("past") else ""
        )
        event = companies_filter.get("timeline")

        count_response += 1
        return_payload = {
            "step": "shorten_prompts",
            "shorten_prompts": {
                "current": shorten_prompt_current,
                "past": shorten_prompt_past,
                "event": event,
            },
            "response_id": count_response,
        }
        yield last_converter(return_payload)
        count_response += 1

        titles_location_companies_tasks = [
            titles_handling(titles_dict, aisearch_payload),
            locations_processing(locations_aisearch, aisearch_payload),
            get_new_companies_dict(
                convId,
                promptId,
                aisearch_payload,
                shorten_prompt_current,
                shorten_prompt_past,
                event,
            ),
        ]
    else:
        return_payload = {
            "step": "company_filters",
            "filters_object": companies_filter,
            "response_id": count_response,
        }
        yield last_converter(return_payload)

        titles_location_companies_tasks = [
            titles_handling(titles_dict, aisearch_payload),
            locations_processing(locations_aisearch, aisearch_payload),
        ]

    async for chunk in handling_titles_locations(
        titles_location_companies_tasks, temp_filters, count_response
    ):
        yield chunk

    return


async def processing_aisearch_results_suggestions(
    temp_filters,
    count_response,
    aisearch_payload,
    convId,
    promptId,
    special_handling=True,
):

    locations_aisearch = (
        temp_filters.pop("location") if "location" in temp_filters else {}
    )

    companies_filter = {}
    if temp_filters.get("companies", {}):
        if temp_filters.get("companies", {}).get("current", []):
            if isinstance(temp_filters.get("companies", {}).get("current", [])[0], str):
                companies_filter = temp_filters.pop("companies", {})
        elif temp_filters.get("companies", {}).get("past", []):
            if isinstance(temp_filters.get("companies", {}).get("past", [])[0], str):
                companies_filter = temp_filters.pop("companies", {})

        if isinstance(
            temp_filters.get("companies", {}).get("current", []), str
        ) or isinstance(temp_filters.get("companies", {}).get("past", []), str):
            companies_filter = temp_filters.pop("companies", {})
            companies_filter.update(
                {
                    "current": (
                        [companies_filter.get("current", None)]
                        if companies_filter.get("current", "")
                        else []
                    ),
                    "past": (
                        [companies_filter.get("past", None)]
                        if companies_filter.get("past", "")
                        else []
                    ),
                }
            )

    block_companies = False
    if temp_filters.get("new_companies", {}):
        block_companies = True
        if temp_filters.get("new_companies", {}).get("current", []):
            if isinstance(
                temp_filters.get("new_companies", {}).get("current", [])[0], str
            ):
                companies_filter = temp_filters.pop("new_companies", {})
        elif temp_filters.get("new_companies", {}).get("past", []):
            if isinstance(
                temp_filters.get("new_companies", {}).get("past", [])[0], str
            ):
                companies_filter = temp_filters.pop("new_companies", {})

    titles_dict = temp_filters.get("title")

    location_task = asyncio.create_task(
        locations_processing(locations_aisearch, aisearch_payload)
    )  # creating so it runs in the background
    item = await titles_handling(titles_dict, aisearch_payload)
    titles_dict = item[0]
    if titles_dict:
        temp_filters.update({"title": titles_dict})

    return_payload = {
        "step": "filters",
        "filters_object": temp_filters,
        "response_id": count_response,
    }
    yield last_converter(return_payload)

    item = await location_task
    locations_aisearch = item[0]
    return_payload = {
        "step": "location_filter",
        "filters_object": {"location": locations_aisearch},
        "response_id": count_response,
    }
    yield last_converter(return_payload)

    return_payload = {
        "step": "company_filters",
        "filters_object": companies_filter,
        "response_id": count_response,
    }
    yield last_converter(return_payload)
    return
