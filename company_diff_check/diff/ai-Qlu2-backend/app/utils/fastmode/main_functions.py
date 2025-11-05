import os
import copy
import asyncio
from app.utils.company_generation.mapping import white_death
from app.utils.aisearch_final.aisearch import main as aisearch_main
from app.utils.ai_search_context.context_aisearch import context as context_main
from app.utils.aisearch_final.complete_aisearch import test_main as aisearch_new
from app.utils.fastmode.fs_side_functions import (
    get_profile_suggestions,
    ingest_profile_by_search_term,
    ingest_profiles_identifier,
    map_locations_by_name,
)
from app.utils.fastmode.postgres_functions import (
    insert_into_cache_single_entity_results,
)
from app.utils.fastmode.summary import summary_text
from app.utils.fastmode.helper_functions import (
    build_all_search_strings,
    context_transformation,
    group_entity_steps,
    last_converter,
)
from app.utils.fastmode.streaming_functions import (
    sending_grok_results_back,
    stream_openai_text,
)
from app.utils.fastmode.prompts import (
    LOCATIONS_VERIFIER_AGENT,
    KEYWORD_WITH_TITLE_PROMPT,
)
from app.utils.fastmode.suggestions_utils import (
    requirements_expansion_agent,
    get_new_companies_dict,
)
from app.utils.fastmode.llms import grok, claude
from qutils.llm.agents.industry import breakdown


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
                        "content": f"""<Prompt>\n{aisearch_payload}\n</Prompt>\n<List to Filter>\n{all_locs}\n</List to Filter>""",
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
        titles_location_companies_tasks = [
            titles_handling(titles_dict, aisearch_payload),
            locations_processing(locations_aisearch, aisearch_payload),
            get_new_companies_dict(
                convId,
                promptId,
                aisearch_payload,
                (
                    companies_filter.get("current")[0]
                    if companies_filter.get("current")
                    else ""
                ),
                companies_filter.get("past")[0] if companies_filter.get("past") else "",
                companies_filter.get("timeline"),
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


async def step_plans(
    plan,
    tasks,
    convId,
    promptId,
    main_query,
    index,
    company_keys,
    person_keys,
    count_response,
    es_client,
):
    for index_, entity in enumerate(plan):
        SUB_SECTION = None
        results = []
        count_response += 1
        # index = count_response

        company_identifier = None
        product_allowed = True
        public_symbol = True
        white_death_data = False
        person_key = None
        EXPLANATION_IDENTIFIER = None
        explanation = ""
        yield_on = True
        ENTITY_INDEX = -1
        for step in entity:
            index = index + 1
            results = []
            return_payload = {}
            step_name = step.get("step", "")
            if step_name == "company_mapping":
                esid, source = await white_death(
                    step.get("company", ""),
                    step.get("company", ""),
                    "[]",
                    es_client,
                )
                if (
                    not source.get("li_size", 0) or source.get("li_size", 0) < 5000
                ) and (
                    not source.get("li_staffcount", 0)
                    or source.get("li_staffcount", 0) < 5000
                ):
                    product_allowed = False
                company_identifier = source.get("li_universalname", "")
                continue
            if step_name == "person_mapping":
                payload = (
                    {"names": step.get("person_name", "")}
                    if step.get("person_name", [])
                    else {}
                )
                (
                    payload.update({"titles": step.get("title", "")})
                    if step.get("title", "")
                    else {}
                )
                (
                    payload.update({"companies": step.get("company", "")})
                    if step.get("company", "")
                    else {}
                )
                mapped_locations = await map_locations_by_name(step.get("location", ""))
                temp_locations = [
                    mapped_locations.get(item).get("name") for item in mapped_locations
                ]
                if temp_locations:
                    payload.update({"locations": temp_locations})

                inferred_var = step.get("inferred_variables", [])
                possible_payloads = []

                payload = {
                    k: [v for v in vals if v.strip()]
                    for k, vals in payload.items()
                    if any(v.strip() for v in vals)
                }

                if "timeline" in step and step.get("timeline"):
                    if isinstance(step.get("timeline"), list) and step["timeline"][0]:
                        payload["timeline"] = (
                            step["timeline"][0]
                            if step["timeline"][0].lower()
                            in ["current", "past", "either"]
                            else "either"
                        )
                    elif isinstance(step.get("timeline"), str):
                        payload["timeline"] = (
                            step["timeline"]
                            if step["timeline"].lower() in ["current", "past", "either"]
                            else "either"
                        )

                possible_payloads.append(payload)
                temp_2_payload = copy.deepcopy(payload)
                if "location" in inferred_var and "locations" in payload:
                    temp_payload = copy.deepcopy(payload)
                    temp_payload.pop("locations")
                    temp_2_payload.pop("locations")
                    possible_payloads.append(temp_payload)
                if "name" in inferred_var and "names" in payload:
                    temp_payload = copy.deepcopy(payload)
                    temp_payload.pop("names")
                    temp_2_payload.pop("names")
                    possible_payloads.append(temp_payload)
                if "title" in inferred_var and "titles" in payload:
                    temp_payload = copy.deepcopy(payload)
                    temp_payload.pop("titles")
                    temp_2_payload.pop("titles")
                    possible_payloads.append(temp_payload)
                if "company" in inferred_var and "companies" in payload:
                    temp_payload = copy.deepcopy(payload)
                    temp_payload.pop("companies")
                    temp_2_payload.pop("companies")
                    possible_payloads.append(temp_payload)

                person_identifiers_list = await asyncio.gather(
                    *[get_profile_suggestions(item) for item in possible_payloads]
                )

                person_identifiers = person_identifiers_list[0]
                for v_temp_index, item in enumerate(person_identifiers_list):
                    if not item:
                        continue
                    else:
                        person_identifiers = person_identifiers_list[v_temp_index]
                        break

                public_identifiers = [
                    item.get("public_identifier", "") for item in person_identifiers
                ]

                if not person_identifiers:
                    possible_searches = build_all_search_strings(temp_2_payload)
                    if possible_searches:
                        person_search_terms_list = await asyncio.gather(
                            *[
                                ingest_profile_by_search_term(item)
                                for item in possible_searches
                            ]
                        )
                        for v_temp_index, item in enumerate(person_search_terms_list):
                            if not item:
                                continue
                            else:
                                public_identifiers = list(item.keys())
                                person_identifiers = list(item.keys())
                                break
                if person_identifiers:
                    public_identifiers = list(set(public_identifiers))
                    if len(public_identifiers) == 1:
                        person_key = public_identifiers[0]
                        continue
                    else:
                        person_key = None
                        return_payload = {
                            "step": "person_mapping",
                            "identifiers": public_identifiers,
                            "response_id": index,
                        }
                        results.append(
                            {
                                "Person Mapping Options Presented To User": [
                                    person_identifiers
                                ]
                            }
                        )
                        yield last_converter(return_payload)
                        ENTITY_INDEX = index
                        yield_on = False
                else:
                    return_payload = {
                        "step": "text_line",
                        "text": "We do not have the required information for this person at the moment.",
                        "response_id": index,
                    }
                    results.append(
                        {"text_line": "Person Not Found using the given credentials"}
                    )
                    yield last_converter(return_payload)
                    yield_on = False
                    break

            if step_name == "show_modal":
                if step.get("section", "") == "company":
                    if not step.get("identifier", "") and company_identifier:
                        step["identifier"] = company_identifier
                        white_death_data = True
                    if (
                        step.get("identifier", "")
                        and step.get("identifier", "") != company_identifier
                    ):
                        query = {
                            "query": {
                                "term": {"li_universalname": step.get("identifier", "")}
                            }
                        }
                        results_comp = await es_client.search(
                            body=query, index="company", timeout="60s"
                        )
                        results_comp = results_comp["hits"]["hits"]
                        if len(results_comp) == 0:
                            step["identifier"] = ""

                            if step.get("company", "") and not company_identifier:
                                esid, source = await white_death(
                                    step.get("company", ""),
                                    step.get("company", ""),
                                    "[]",
                                    es_client,
                                )
                                step["identifier"] = source.get("li_universalname", "")
                                white_death_data = True
                            elif company_identifier:
                                step["identifier"] = company_identifier
                                white_death_data = True
                        else:
                            li_size = results_comp[0]["_source"].get("li_size", 0)
                            li_staffcount = results_comp[0]["_source"].get(
                                "li_staffcount", 0
                            )
                            if li_size < 5000 and li_staffcount < 5000:
                                product_allowed = False

                            if not results_comp[0]["_source"].get(
                                "cb_stock_symbol", ""
                            ):
                                public_symbol = False
                                white_death_data = False

                    if step.get("sub_section", "") in ["Products"]:
                        if not step.get("identifier", "") or not product_allowed:
                            return_payload = {
                                "step": "text_line",
                                "text": "We do not have the product information for this company at the moment.",
                                "response_id": index,
                            }
                            yield last_converter(return_payload)
                            results.append(return_payload)

                    elif step.get("sub_section", "") in [
                        "Reports",
                        "Business Units",
                        "News",
                    ]:
                        if white_death_data and step.get("identifier", ""):
                            query = {
                                "_source": ["cb_stock_symbol"],
                                "query": {
                                    "term": {
                                        "li_universalname": step.get("identifier", "")
                                    }
                                },
                            }
                            results_comp = await es_client.search(
                                body=query, index="company", timeout="60s"
                            )
                            if not results_comp["hits"]["hits"][0]["_source"].get(
                                "cb_stock_symbol", ""
                            ):
                                public_symbol = False

                        if not step.get("identifier", "") or not public_symbol:
                            return_payload = {
                                "step": "text_line",
                                "text": "We do not have the required information for this company at the moment.",
                                "response_id": index,
                            }
                            results.append({"Company_Extraction": return_payload})
                            yield last_converter(return_payload)
                            continue

                    elif not step.get("identifier", ""):
                        return_payload = {
                            "step": "text_line",
                            "text": "We do not have the required information for this company at the moment.",
                            "response_id": index,
                        }
                        results.append(
                            {
                                "Company_Extraction": "Company not found in database in 1st try"
                            }
                        )
                        yield last_converter(return_payload)
                        continue

                    if step.get("sub_section", None) in company_keys.keys():
                        step["sub_section"] = company_keys[step["sub_section"]]
                    else:
                        continue
                    return_payload = step
                    results.append({"Company_Extraction": return_payload})
                    return_payload["response_id"] = index
                    yield last_converter(return_payload)

                if step.get("section", "") == "person":
                    step["sub_section"] = person_keys.get(
                        step.get("sub_section", ""), ""
                    )

                    SUB_SECTION = step["sub_section"]
                    if step.get("identifier", ""):
                        identifier = step.get("identifier", "")
                        query = {
                            "_source": ["full_name"],
                            "query": {"term": {"public_identifier": identifier}},
                        }
                        results_comp = await es_client.search(
                            body=query,
                            index=os.getenv("ES_PROFILES_INDEX", "people"),
                            timeout="60s",
                        )

                        results_comp = results_comp["hits"]["hits"]
                        if len(results_comp) == 0:
                            ingest_into_db = await ingest_profiles_identifier(
                                [step.get("identifier", "")]
                            )
                            esid = ingest_into_db.get(identifier, None)
                            if not esid:
                                identifier = None
                                step["identifier"] = None
                        else:
                            name = step.get("name", "")
                            if not name:
                                name = results_comp[0]["_source"]["full_name"]
                                step["name"] = name

                    if person_key and not step.get("identifier", ""):
                        step["identifier"] = person_key

                    EXPLANATION_IDENTIFIER = step["identifier"]

                    # if unique_identifier:
                    #     step["unique_identifier"] = unique_identifier

                    return_payload = step
                    if step.get("identifier", "") and yield_on:
                        return_payload["response_id"] = index
                        yield last_converter(return_payload)
                    elif not step.get("identifier") and yield_on:
                        return_payload = {
                            "step": "text_line",
                            "text": "We do not have the required information for this person at the moment.",
                            "response_id": index,
                        }
                        results.append(
                            {
                                "text_line": "Person Not Found using the given credentials"
                            }
                        )
                        yield last_converter(return_payload)
                        break
                    results.append(
                        {
                            "Person_Modal": return_payload,
                            "Entity_Number": index_ + 1,
                        }
                    )

            if step_name == "text_line_description":
                if yield_on:
                    if EXPLANATION_IDENTIFIER:
                        explanation = await summary_text(
                            EXPLANATION_IDENTIFIER,
                            step.get("entity", ""),
                            "",
                            main_query,
                            es_client,
                        )  # SUB_SECTION
                        if explanation:
                            sum_of_text = ""
                            async for chunk in stream_openai_text(explanation):
                                return_payload = {
                                    "step": "text_line",
                                    "text": chunk,
                                    "response_id": index,
                                }
                                yield last_converter(return_payload)
                                sum_of_text += chunk

                            results.append({"Text Shown": sum_of_text})
                            yield last_converter(
                                {
                                    "step": "text_line",
                                    "text": "\n\n",
                                    "response_id": index,
                                }
                            )
                        else:
                            continue
                    else:
                        continue
                else:
                    step["SUB_SECTION"] = SUB_SECTION
                    results.append(step)

            if step_name == "text_line":
                if yield_on:
                    sum_of_text = ""
                    async for chunk in stream_openai_text(step.get("text", "")):
                        return_payload = {
                            "step": "text_line",
                            "text": chunk,
                            "response_id": index,
                        }
                        sum_of_text += chunk
                        yield last_converter(return_payload)
                    results.append({"Text Shown": sum_of_text})
                else:
                    results.append(step)

            if results:
                if not yield_on and index != ENTITY_INDEX:
                    tasks.append(
                        asyncio.create_task(
                            insert_into_cache_single_entity_results(
                                convId,
                                promptId,
                                index - 1,
                                main_query,
                                results[0],
                                temp=True,
                            )
                        )
                    )
                else:
                    tasks.append(
                        asyncio.create_task(
                            insert_into_cache_single_entity_results(
                                convId, promptId, index, main_query, results[0]
                            )
                        )
                    )
    return


async def calling_aisearch_without_saving(
    aisearch_payload,
    convId,
    promptId,
    es_client,
    qdrant_client,
    demoBlocked,
    add_to_clear_prompt="",
):

    # subtasks = [
    #     asyncio.create_task(
    #         dual_shorten_prompt(aisearch_payload, use_legacy_prompt=False)
    #     ),
    #     asyncio.create_task(
    #         aisearch_main(
    #             aisearch_payload,
    #             es_client,
    #             demoBlocked=demoBlocked,
    #             return_type=True,
    #         )
    #     ),
    # ]

    asyncio.create_task(
        suggestions_preparations(
            aisearch_payload, convId, promptId, es_client, demoBlocked=demoBlocked
        )
    )

    results = await asyncio.create_task(
        aisearch_new(
            aisearch_payload,
            es_client,
            qdrant_client,
            demoBlocked=demoBlocked,
            add_to_clear_prompt=add_to_clear_prompt,
        )
    )
    return results


async def single_entity_processing(
    response_entity,
    tasks,
    convId,
    promptId,
    main_query,
    index,
    company_keys,
    person_keys,
    count_response,
    es_client,
):
    plan = group_entity_steps(response_entity.get("plan", []))
    if len(plan) < 6:
        async for chunk in step_plans(
            plan,
            tasks,
            convId,
            promptId,
            main_query,
            index,
            company_keys,
            person_keys,
            count_response,
            es_client,
        ):
            yield chunk
        return


async def processing_modification(
    count_response,
    ambiguity,
    demoBlocked,
    aisearch,
    convId,
    promptId,
    main_query,
    fast_reply,
):
    count_response += 1
    aisearch_payload = ambiguity.get("clear_prompt", "")
    if "attributes" in ambiguity:
        ambiguity = context_transformation(ambiguity, demoBlocked=demoBlocked)
    action = ambiguity.get("action", "extract")
    filters = ambiguity.get("attributes", [])
    indexes = ambiguity.get("indexes", [])
    subtasks = []
    if action.lower() == "modify":
        if indexes and filters:

            context = [aisearch.get(j_ind) for j_ind in indexes if j_ind in aisearch]
            if context:

                count_response += 1

                last_applied_filters = context[-1].get("result")

                return_payload = {
                    "step": "filters",
                    "filters_object": last_applied_filters,
                    "filters_to_modify": filters,
                    "response_id": count_response,
                }
                yield last_converter(return_payload)

                subtasks = [
                    context_main(aisearch_payload, context, filter_, return_entity=True)
                    for filter_ in filters
                ]

    if subtasks:
        total_modified = []
        for coro in asyncio.as_completed(subtasks):
            item, entity = await coro

            if "location" in item:
                location_all = list(item.get("location", {}).get("filter", {}).keys())

                mapped_locations = await map_locations_by_name(location_all)
                for key in list(item.get("location", {}).get("filter", {})):
                    if mapped_locations.get(key):
                        item["location"]["filter"][mapped_locations[key]["name"]] = (
                            item["location"]["filter"].pop(key)
                        )

                        item["location"]["filter"][mapped_locations[key]["name"]][
                            "urn"
                        ] = mapped_locations[key].get("urn", None)
                        item["location"]["filter"][mapped_locations[key]["name"]][
                            "id"
                        ] = mapped_locations[key].get("id", None)
                    else:
                        item["location"]["filter"].pop(key)
            return_payload = {
                "step": "filter_modification",
                "filters_object": item,
                "modified_filter": entity,
                "response_id": count_response,
            }
            total_modified.append(return_payload)
            yield last_converter(return_payload)
        results = []
        results.append(
            {
                "AI_Search_Results": total_modified,
                "clear_prompt": aisearch_payload,
            }
        )
        asyncio.create_task(
            insert_into_cache_single_entity_results(
                convId, promptId, count_response, main_query, results[0]
            )
        )
    else:
        yield "None"
    return


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

        titles_location_companies_tasks = [
            titles_handling(titles_dict, aisearch_payload),
            locations_processing(locations_aisearch, aisearch_payload),
            get_new_companies_dict(
                convId,
                promptId,
                main_query,
                (
                    companies_dict.get("current")[0]
                    if companies_dict.get("current")
                    else ""
                ),
                companies_dict.get("past")[0] if companies_dict.get("past") else "",
                companies_dict.get("timeline"),
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


async def handling_fast_reply(fast_reply, response_id):
    if fast_reply.get("ambiguity", 0):
        prompt_to_show = fast_reply.get("follow_up", "")
    else:
        prompt_to_show = fast_reply.get("clear_prompt", "")

    async for chunk in sending_grok_results_back(prompt_to_show, response_id):
        yield chunk

    return
