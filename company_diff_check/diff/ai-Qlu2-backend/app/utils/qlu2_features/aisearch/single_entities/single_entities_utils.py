import os
import copy
import asyncio
from app.utils.search.aisearch.company.generation.mapping import white_death

from app.utils.qlu2_features.aisearch.utilities.helper_functions.fs_side_functions import (
    get_profile_suggestions,
    ingest_profile_by_search_term,
    ingest_profiles_identifier,
    map_locations_by_name,
)
from app.utils.qlu2_features.aisearch.utilities.helper_functions.postgres_functions import (
    insert_into_cache_single_entity_results,
)
from app.utils.qlu2_features.aisearch.utilities.general.summary import summary_text
from app.utils.qlu2_features.aisearch.utilities.helper_functions.misc_functions import (
    build_all_search_strings,
    last_converter,
)
from app.utils.qlu2_features.aisearch.utilities.helper_functions.streaming_functions import (
    stream_openai_text,
)


def group_entity_steps(steps):
    plan = []
    current_entity = []

    for step in steps:
        if step["step"] == "entity_complete":
            if current_entity:
                plan.append(current_entity)
                current_entity = []
        else:
            current_entity.append(step)

    if current_entity:
        if plan[-1]:
            plan[-1] += current_entity
        else:
            plan.append(current_entity)
    return plan


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
        SIMILAR_PROFILES_FLAG = False
        for step_num, step in enumerate(entity):
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
                        "text": "Person Not Found using the given credentials",
                        "response_id": index,
                    }
                    results.append(
                        {"text_line": "Person Not Found using the given credentials\n"}
                    )
                    yield last_converter(return_payload)

                    if step_num + 1 < len(entity):
                        SIMILAR_PROFILES_FLAG = False
                        for modal in entity[step_num + 1 :]:

                            if (
                                modal.get("step", "") == "show_modal"
                                and modal.get("section", "") == "person"
                                and modal.get("sub_section", "") == "similar_profiles"
                            ):
                                SIMILAR_PROFILES_FLAG = True

                        if SIMILAR_PROFILES_FLAG:
                            explanation = await summary_text(
                                None,
                                "person",
                                "",
                                main_query,
                                es_client,
                                SIMILAR_PROFILES_FLAG,
                            )
                            if explanation:
                                index = index + 1
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
                                tasks.append(
                                    asyncio.create_task(
                                        insert_into_cache_single_entity_results(
                                            convId, promptId, index, main_query, results
                                        )
                                    )
                                )

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
                    if step.get("sub_section", "") == "similar_profiles":
                        SIMILAR_PROFILES_FLAG = True
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
                            SIMILAR_PROFILES_FLAG,
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
