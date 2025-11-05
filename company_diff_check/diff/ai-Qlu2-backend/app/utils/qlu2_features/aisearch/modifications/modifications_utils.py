import os
import copy
import asyncio
from app.utils.search.aisearch.company.generation.mapping import white_death
from app.utils.aisearch_final.aisearch import main as aisearch_main
from app.utils.ai_search_context.context_aisearch import context as context_main
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
    context_transformation,
    group_entity_steps,
    last_converter,
)
from app.utils.qlu2_features.aisearch.utilities.helper_functions.streaming_functions import (
    sending_grok_results_back,
    stream_openai_text,
)

from app.utils.qlu2_features.aisearch.suggestions.suggestions_utils import (
    get_new_companies_dict,
)
from app.utils.qlu2_features.aisearch.suggestions.suggestions_agents import (
    requirements_expansion_agent,
)


async def processing_modification(
    count_response,
    ambiguity,
    demoBlocked,
    aisearch,
    convId,
    promptId,
    main_query,
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
