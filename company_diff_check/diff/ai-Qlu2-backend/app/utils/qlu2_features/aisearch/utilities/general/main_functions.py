# import os
# import copy
# import asyncio
# from app.utils.company_generation.mapping import white_death
# from app.utils.aisearch_final.aisearch import main as aisearch_main
# from app.utils.ai_search_context.context_aisearch import context as context_main
# from app.utils.aisearch_final.complete_aisearch import test_main as aisearch_new
# from app.utils.qlu2_features.aisearch.utilities.helper_functions.fs_side_functions import (
#     get_profile_suggestions,
#     ingest_profile_by_search_term,
#     ingest_profiles_identifier,
#     map_locations_by_name,
# )
# from app.utils.qlu2_features.aisearch.utilities.helper_functions.postgres_functions import (
#     insert_into_cache_single_entity_results,
# )
# from app.utils.qlu2_features.aisearch.utilities.general.summary import summary_text
# from app.utils.qlu2_features.aisearch.utilities.helper_functions.misc_functions import (
#     build_all_search_strings,
#     context_transformation,
#     group_entity_steps,
#     last_converter,
# )
# from app.utils.qlu2_features.aisearch.utilities.helper_functions.streaming_functions import (
#     sending_grok_results_back,
#     stream_openai_text,
# )
# from app.utils.qlu2_features.aisearch.filters.filters_prompts import (
#     LOCATIONS_VERIFIER_AGENT,
#     KEYWORD_WITH_TITLE_PROMPT,
# )
# from app.utils.qlu2_features.aisearch.suggestions.suggestions_utils import (
#     get_new_companies_dict,
# )
# from app.utils.qlu2_features.aisearch.suggestions.suggestions_agents import (
#     requirements_expansion_agent,
# )
# from app.utils.qlu2_features.aisearch.utilities.llm_functions.llms import grok, claude
# from qutils.llm.agents import industry_breakdown


# async def processing_aisearch_results_suggestions(
#     temp_filters,
#     count_response,
#     aisearch_payload,
#     convId,
#     promptId,
#     special_handling=True,
# ):

#     locations_aisearch = (
#         temp_filters.pop("location") if "location" in temp_filters else {}
#     )

#     companies_filter = {}
#     if temp_filters.get("companies", {}):
#         if temp_filters.get("companies", {}).get("current", []):
#             if isinstance(temp_filters.get("companies", {}).get("current", [])[0], str):
#                 companies_filter = temp_filters.pop("companies", {})
#         elif temp_filters.get("companies", {}).get("past", []):
#             if isinstance(temp_filters.get("companies", {}).get("past", [])[0], str):
#                 companies_filter = temp_filters.pop("companies", {})

#         if isinstance(
#             temp_filters.get("companies", {}).get("current", []), str
#         ) or isinstance(temp_filters.get("companies", {}).get("past", []), str):
#             companies_filter = temp_filters.pop("companies", {})
#             companies_filter.update(
#                 {
#                     "current": (
#                         [companies_filter.get("current", None)]
#                         if companies_filter.get("current", "")
#                         else []
#                     ),
#                     "past": (
#                         [companies_filter.get("past", None)]
#                         if companies_filter.get("past", "")
#                         else []
#                     ),
#                 }
#             )

#     block_companies = False
#     if temp_filters.get("new_companies", {}):
#         block_companies = True
#         if temp_filters.get("new_companies", {}).get("current", []):
#             if isinstance(
#                 temp_filters.get("new_companies", {}).get("current", [])[0], str
#             ):
#                 companies_filter = temp_filters.pop("new_companies", {})
#         elif temp_filters.get("new_companies", {}).get("past", []):
#             if isinstance(
#                 temp_filters.get("new_companies", {}).get("past", [])[0], str
#             ):
#                 companies_filter = temp_filters.pop("new_companies", {})

#     titles_dict = temp_filters.get("title")

#     location_task = asyncio.create_task(
#         locations_processing(locations_aisearch, aisearch_payload)
#     )  # creating so it runs in the background
#     item = await titles_handling(titles_dict, aisearch_payload)
#     titles_dict = item[0]
#     if titles_dict:
#         temp_filters.update({"title": titles_dict})

#     return_payload = {
#         "step": "filters",
#         "filters_object": temp_filters,
#         "response_id": count_response,
#     }
#     yield last_converter(return_payload)

#     item = await location_task
#     locations_aisearch = item[0]
#     return_payload = {
#         "step": "location_filter",
#         "filters_object": {"location": locations_aisearch},
#         "response_id": count_response,
#     }
#     yield last_converter(return_payload)

#     return_payload = {
#         "step": "company_filters",
#         "filters_object": companies_filter,
#         "response_id": count_response,
#     }
#     yield last_converter(return_payload)
#     return


# async def calling_aisearch_without_saving(
#     aisearch_payload, convId, promptId, es_client, demoBlocked, add_to_clear_prompt=""
# ):

#     # subtasks = [
#     #     asyncio.create_task(
#     #         dual_shorten_prompt(aisearch_payload, use_legacy_prompt=False)
#     #     ),
#     #     asyncio.create_task(
#     #         aisearch_main(
#     #             aisearch_payload,
#     #             es_client,
#     #             demoBlocked=demoBlocked,
#     #             return_type=True,
#     #         )
#     #     ),
#     # ]

#     asyncio.create_task(
#         suggestions_preparations(
#             aisearch_payload, convId, promptId, es_client, demoBlocked=demoBlocked
#         )
#     )

#     results = await asyncio.create_task(
#         aisearch_new(
#             aisearch_payload,
#             es_client,
#             demoBlocked=demoBlocked,
#             add_to_clear_prompt=add_to_clear_prompt,
#         )
#     )
#     return results


# async def single_entity_processing(
#     response_entity,
#     tasks,
#     convId,
#     promptId,
#     main_query,
#     index,
#     company_keys,
#     person_keys,
#     count_response,
#     es_client,
# ):
#     plan = group_entity_steps(response_entity.get("plan", []))
#     if len(plan) < 6:
#         async for chunk in step_plans(
#             plan,
#             tasks,
#             convId,
#             promptId,
#             main_query,
#             index,
#             company_keys,
#             person_keys,
#             count_response,
#             es_client,
#         ):
#             yield chunk
#         return


# async def processing_modification(
#     count_response,
#     ambiguity,
#     demoBlocked,
#     aisearch,
#     convId,
#     promptId,
#     main_query,
# ):
#     count_response += 1
#     aisearch_payload = ambiguity.get("clear_prompt", "")
#     if "attributes" in ambiguity:
#         ambiguity = context_transformation(ambiguity, demoBlocked=demoBlocked)
#     action = ambiguity.get("action", "extract")
#     filters = ambiguity.get("attributes", [])
#     indexes = ambiguity.get("indexes", [])
#     subtasks = []
#     if action.lower() == "modify":
#         if indexes and filters:

#             context = [aisearch.get(j_ind) for j_ind in indexes if j_ind in aisearch]
#             if context:

#                 count_response += 1

#                 last_applied_filters = context[-1].get("result")

#                 return_payload = {
#                     "step": "filters",
#                     "filters_object": last_applied_filters,
#                     "filters_to_modify": filters,
#                     "response_id": count_response,
#                 }
#                 yield last_converter(return_payload)

#                 subtasks = [
#                     context_main(aisearch_payload, context, filter_, return_entity=True)
#                     for filter_ in filters
#                 ]

#     if subtasks:
#         total_modified = []
#         for coro in asyncio.as_completed(subtasks):
#             item, entity = await coro

#             if "location" in item:
#                 location_all = list(item.get("location", {}).get("filter", {}).keys())

#                 mapped_locations = await map_locations_by_name(location_all)
#                 for key in list(item.get("location", {}).get("filter", {})):
#                     if mapped_locations.get(key):
#                         item["location"]["filter"][mapped_locations[key]["name"]] = (
#                             item["location"]["filter"].pop(key)
#                         )

#                         item["location"]["filter"][mapped_locations[key]["name"]][
#                             "urn"
#                         ] = mapped_locations[key].get("urn", None)
#                         item["location"]["filter"][mapped_locations[key]["name"]][
#                             "id"
#                         ] = mapped_locations[key].get("id", None)
#                     else:
#                         item["location"]["filter"].pop(key)
#             return_payload = {
#                 "step": "filter_modification",
#                 "filters_object": item,
#                 "modified_filter": entity,
#                 "response_id": count_response,
#             }
#             total_modified.append(return_payload)
#             yield last_converter(return_payload)
#         results = []
#         results.append(
#             {
#                 "AI_Search_Results": total_modified,
#                 "clear_prompt": aisearch_payload,
#             }
#         )
#         asyncio.create_task(
#             insert_into_cache_single_entity_results(
#                 convId, promptId, count_response, main_query, results[0]
#             )
#         )
#     else:
#         yield "None"
#     return


# async def new_aisearch_results(
#     aisearch_payload, temp_filters, count_response, convId, promptId, main_query
# ):
#     aisearch_results = []
#     locations_aisearch = {}
#     # for coro in asyncio.as_completed(subtasks):

#     # if isinstance(temp_filters, tuple):
#     aisearch_results.append(temp_filters)

#     locations_aisearch = (
#         temp_filters.pop("location") if "location" in temp_filters else {}
#     )

#     companies_dict = temp_filters.pop("companies", {})
#     titles_dict = temp_filters.get("title")

#     if titles_dict and titles_dict.get("event"):
#         if companies_dict and companies_dict.get("timeline"):
#             titles_event = titles_dict.get("event")
#             companies_event = companies_dict.get("timeline")
#             accepted = ["OR", "CURRENT"]
#             if titles_event in accepted and companies_event in accepted:
#                 companies_event = titles_event
#             companies_dict["timeline"] = companies_event

#     if companies_dict:

#         titles_location_companies_tasks = [
#             titles_handling(titles_dict, aisearch_payload),
#             locations_processing(locations_aisearch, aisearch_payload),
#             get_new_companies_dict(
#                 convId,
#                 promptId,
#                 main_query,
#                 (
#                     companies_dict.get("current")[0]
#                     if companies_dict.get("current")
#                     else ""
#                 ),
#                 companies_dict.get("past")[0] if companies_dict.get("past") else "",
#                 companies_dict.get("timeline"),
#             ),
#         ]
#     else:
#         return_payload = {
#             "step": "company_filters",
#             "filters_object": companies_dict,
#             "response_id": count_response,
#         }
#         yield last_converter(return_payload)

#         titles_location_companies_tasks = [
#             titles_handling(titles_dict, aisearch_payload),
#             locations_processing(locations_aisearch, aisearch_payload),
#         ]

#     async for chunk in handling_titles_locations(
#         titles_location_companies_tasks, temp_filters, count_response
#     ):
#         yield chunk

#     results = []
#     results.append(
#         {
#             "AI_Search_Results": aisearch_results,
#             "clear_prompt": aisearch_payload,
#         }
#     )
#     asyncio.create_task(
#         insert_into_cache_single_entity_results(
#             convId, promptId, count_response, main_query, results[0]
#         )
#     )
#     return


# async def handling_fast_reply(fast_reply, response_id):
#     if fast_reply.get("ambiguity", 0):
#         prompt_to_show = fast_reply.get("follow_up", "")
#     else:
#         prompt_to_show = fast_reply.get("clear_prompt", "")

#     async for chunk in sending_grok_results_back(prompt_to_show, response_id):
#         yield chunk

#     return
