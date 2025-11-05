import asyncio
from app.core.database import postgres_fetch
from app.utils.aisearch_expansion_variants.variants import *
from app.utils.aisearch_expansion_variants.expansion import *
import copy

from app.utils.qlu2_features.aisearch.utilities.helper_functions.fs_side_functions import (
    map_locations_by_name,
)
from app.utils.qlu2_features.aisearch.utilities.helper_functions.postgres_functions import (
    insert_into_cache_single_entity_results,
    postgres_fetch_custom,
)
from app.utils.qlu2_features.aisearch.utilities.helper_functions.misc_functions import (
    convert_companies,
    last_converter,
)


async def call_for_expansion(
    conversation_id, prompt_id, response_id_temp, es_client, filters=None, prompt=""
):
    if not filters:
        query = f"""
            SELECT DISTINCT prompt
            FROM single_entity_aisearch_new
            WHERE conversation_id = '{conversation_id}'
        """

        query_result = f"""
            SELECT result
            FROM single_entity_aisearch_new
            WHERE conversation_id = '{conversation_id}'
            AND prompt_id = '{prompt_id}'
            AND response_id = '{response_id_temp}'
        """

        prompts_, result_ = await asyncio.gather(
            *[postgres_fetch_custom(query), postgres_fetch(query_result)]
        )
        result = result_[0]
        if result:
            aisearch_results = result.get("AI_Search_Results", "")
        else:
            aisearch_results = None
    else:
        query = f"""
            SELECT DISTINCT prompt
            FROM single_entity_aisearch_new
            WHERE conversation_id = '{conversation_id}'
        """

        prompts_ = await postgres_fetch_custom(query)
        aisearch_results = filters

    queries = [item[0] for item in prompts_]
    if not queries and prompt:
        queries = [prompt]

    if not queries:
        yield ""
        return

    if (
        aisearch_results.get("companies", None)
        and not aisearch_results.get("industry", None)
    ) or aisearch_results.get("title", None):
        expansion_results = await expansion(aisearch_results, queries, es_client)
        aisearch_results.update(expansion_results)

    return_payload = {
        "step": "filters",
        "filters_object": aisearch_results,
        "response_id": response_id_temp,
    }
    yield last_converter(return_payload)
    return


async def call_for_variants(
    conversation_id,
    prompt_id,
    response_id_temp,
    es_client,
    result_db=None,
):
    response_count = response_id_temp + 10
    if (
        result_db
        and "selectedIndustries" in result_db
        and result_db.get("selectedIndustries", None)
    ):
        query_result = f"""
        SELECT result
        FROM single_entity_aisearch_new_temp
        WHERE conversation_id = '{conversation_id}'
        AND prompt_id = '{prompt_id}'
        AND response_id = '{response_id_temp}'
    """
    else:
        query_result = f"""
        SELECT result
        FROM single_entity_aisearch_new
        WHERE conversation_id = '{conversation_id}'
        AND prompt_id = '{prompt_id}'
        AND response_id = '{response_id_temp}'
    """
    query = f"""
        SELECT DISTINCT prompt
        FROM single_entity_aisearch_new
        WHERE conversation_id = '{conversation_id}'
    """

    prompts_, result_ = await asyncio.gather(
        *[postgres_fetch_custom(query), postgres_fetch(query_result)]
    )

    queries = [item[0] for item in prompts_]
    result = result_[0]

    if not result or not queries:
        yield ""
        return

    count_index = 0

    aisearch_results = result.get("AI_Search_Results", "")
    if result_db and isinstance(result_db, dict):
        aisearch_results.update(result_db)
    if aisearch_results.get("industry", None) or aisearch_results.get(
        "selectedIndustries", None
    ):

        company_filter_return_template = {
            "step": "company_filters",
            "filters_object": {"current": None, "past": None, "timeline": None},
        }
        if aisearch_results.get("selectedIndustries", None):
            count_index = -1
        else:
            count_index = 0

        variants_results_fetch = await variants(aisearch_results, queries, es_client)

        temp_aisearch = copy.deepcopy(aisearch_results)
        sent_flag = False
        for key, value in variants_results_fetch.items():
            if value:
                count_index += 1

                if key == "company":
                    transformation = convert_companies(
                        value.get("companiesCurrent", []),
                        value.get("companiesPast", []),
                        temp_aisearch.get("companies", {}),
                        temp_aisearch.get("companies", {}).get("event", "AND"),
                    )

                    if transformation:
                        temp_aisearch.update({"companies": transformation})
                        # return_payload = {
                        #     "step": "variant",
                        #     "variant_name": key,
                        #     "variant_result": temp_aisearch,
                        #     "response_id": response_count + 1,
                        # }
                        return_payload = {
                            "step": "filters",
                            "filters_object": temp_aisearch,
                            "response_id": response_count + count_index,
                            "description": "More companies have been added to your list to expand your search",
                        }
                        yield last_converter(return_payload)
                        company_filter_return_template["response_id"] = (
                            response_count + count_index
                        )
                        yield last_converter(company_filter_return_template)
                    continue

                temp_aisearch.update(value)
                if key == "industry_company":
                    # return_payload = {
                    #     "step": "variant",
                    #     "variant_name": key,
                    #     "variant_result": value,
                    #     "response_id": response_count + 2,
                    # }

                    return_payload = {
                        "step": "filters",
                        "filters_object": temp_aisearch,
                        "response_id": response_count + count_index,
                        "description": "Search has been expanded with relevant industries",
                    }
                    yield last_converter(return_payload)
                    company_filter_return_template["response_id"] = (
                        response_count + count_index
                    )
                    yield last_converter(company_filter_return_template)

                elif key == "title_or":
                    # return_payload = {
                    #     "step": "variant",
                    #     "variant_name": key,
                    #     "variant_result": value,
                    #     "response_id": response_count + 3,
                    # }
                    # if temp_aisearch.get("past", []) and temp_aisearch.get("current"):

                    temp_aisearch["companies"]["current"] += [
                        item
                        for item in temp_aisearch["companies"]["past"]
                        if item not in temp_aisearch["companies"]["current"]
                    ]
                    temp_aisearch["companies"]["past"] = []

                    if temp_aisearch.get("companies", {}).get("event"):
                        temp_aisearch["companies"]["event"] = "OR"

                    return_payload = {
                        "step": "filters",
                        "filters_object": temp_aisearch,
                        "response_id": response_count + count_index,
                        "description": "Search expanded to include 'Current OR Past' job titles and companies",
                    }
                    yield last_converter(return_payload)
                    company_filter_return_template["response_id"] = (
                        response_count + count_index
                    )
                    yield last_converter(company_filter_return_template)
                elif key == "title_expansion":
                    # return_payload = {
                    #     "step": "variant",
                    #     "variant_name": key,
                    #     "variant_result": value,
                    #     "response_id": response_count + 4,
                    # }

                    return_payload = {
                        "step": "filters",
                        "filters_object": temp_aisearch,
                        "response_id": response_count + count_index,
                        "description": "Search has been expanded with more relevant job titles",
                    }
                    yield last_converter(return_payload)
                    company_filter_return_template["response_id"] = (
                        response_count + count_index
                    )
                    yield last_converter(company_filter_return_template)
                elif key == "location_expansion":
                    # return_payload = {
                    #     "step": "variant",
                    #     "variant_name": key,
                    #     "variant_result": value,
                    #     "response_id": response_count + 5,
                    # }
                    all_locations = list(
                        value.get("location", {}).get("filter", {}).keys()
                    )
                    mapped_locations = await map_locations_by_name(all_locations)
                    for key in list(value.get("location", {}).get("filter", {})):
                        if mapped_locations.get(key, None):
                            value["location"]["filter"][
                                mapped_locations[key]["name"]
                            ] = value["location"]["filter"].pop(key)

                            value["location"]["filter"][mapped_locations[key]["name"]][
                                "urn"
                            ] = mapped_locations[key].get("urn", None)

                            value["location"]["filter"][mapped_locations[key]["name"]][
                                "id"
                            ] = mapped_locations[key].get("id", None)
                        else:
                            value["location"]["filter"].pop(key)

                    temp_aisearch.update(value)
                    return_payload = {
                        "step": "filters",
                        "filters_object": temp_aisearch,
                        "response_id": response_count + count_index,
                        "description": "More locations have been added to your list to expand your search",
                    }
                    yield last_converter(return_payload)
                    company_filter_return_template["response_id"] = (
                        response_count + count_index
                    )
                    yield last_converter(company_filter_return_template)
    else:
        industries = await industry_suggestions(aisearch_results, queries, es_client)
        return_payload = {
            "step": "industry_suggestions",
            "industries": industries,
            "response_id": response_count + 1,
        }
        yield last_converter(return_payload)

        asyncio.create_task(
            insert_into_cache_single_entity_results(
                conversation_id,
                prompt_id,
                response_count + 1,
                "TEMPORARY_SUGGESTIONS",
                {
                    "AI_Search_Results": aisearch_results,
                    "Suggested_Industries": industries,
                },
                temp=True,
            )
        )
    return
