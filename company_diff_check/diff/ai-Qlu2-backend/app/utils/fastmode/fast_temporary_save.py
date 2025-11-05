# async def main(convId, promptId, main_query, es_client, demoBlocked=False):

#     if demoBlocked:
#         from app.utils.fastmode.prompts_no_demo import (
#             ADD_TO_USER_PROMPT,
#             DO_SOMETHING_PROMPT,
#             SINGLE_ENTITY_DETECTION,
#             AMBIGUOUS_PROMPT_AISEARCH,
#             AMBIGUOUS_PROMPT_AISEARCH_INDUSTRY,
#         )
#     else:
#         from app.utils.fastmode.prompts import (
#             ADD_TO_USER_PROMPT,
#             DO_SOMETHING_PROMPT,
#             SINGLE_ENTITY_DETECTION,
#             AMBIGUOUS_PROMPT_AISEARCH,
#             AMBIGUOUS_PROMPT_AISEARCH_INDUSTRY,
#         )

#     string_second_string = ""
#     aisearch = None
#     industry_flag = False
#     if promptId > 1:
#         string_second_string, aisearch, industry_flag = (
#             await fetch_from_cache_single_entity_results(convId, promptId, demoBlocked)
#         )
#     if string_second_string:
#         user_prompt = f"""<Whole_Conversation>\n{string_second_string}<Last_Query>\n{main_query}\n</Last_Query>\n<Whole_Conversation>\n Consider ALL the previous queries and their results as well. Consider that system follow ups were asked to the user by your brother agent; the new query would be a reply to that question so if the user is clarifying something from before then you must take the WHOLE relevant conversation into account BUT do not repeat questions regarding the ambiguity (if the user hasn't clarified something before then keep ambiguity 0 and write the clear prompt keeping the words close to what the user has used till now). Take a deep breath and reason logically about how the new prompt relates to the previous ones to make a very relevant follow_up or clear_prompt and NEVER lose context unless you're sure the new query is not related to the previous as the results are going to be generated based on the clear_prompt which must contain the context of the complete conversation."""

#         user_prompt_single = f"""<Whole_Conversation>\n{string_second_string}<Last_Query>\n{main_query}\n</Last_Query>\n<Whole_Conversation>\n Consider ALL the previous queries and their results as well. Consider that system follow ups were asked to the user by your brother agent; if the user is clarifying something from before then you must take the WHOLE relevant conversation into account. Take a deep breath and reason logically about how and whether the new prompt relates to the previous ones (can also use identifiers if you know of them)."""
#     else:
#         user_prompt = f"""<User_Prompt>\n{main_query}\n</User_Prompt>"""
#         user_prompt_single = user_prompt

#     # print("aisearch\n", aisearch, "\n\n")

#     person_keys = {
#         "summary": "summary",
#         "experience": "experience",
#         "information": "contact",
#         "pay_progression": "pay",
#         "similar_profiles": "similar_profiles",
#         "education": "education",
#         "skills": "skills",
#         "industries": "industries",
#     }
#     company_keys = {
#         "summary": "summary",
#         "financials": "financials",
#         "m&a": "m&a",
#         "leadership": "leadership",
#         "competitors": "competitors",
#         "reports": "reports",
#         "business_units": "business_units",
#         "news": "news",
#         "products": "products",
#     }

#     """"""
#     PERSON_INCLUDED_PROMPT = 1000
#     do_something_prompt = (
#         DO_SOMETHING_PROMPT
#         + "\n**If the user has been asked a follow-up question by the system before and they haven't answered, do NOT ask them again and just rewrite the clear_prompt in words as close to what the user has said**. Take the previous conversation into account; if the new prompt can be a continuation, it likely is one. The follow up or clear prompt MUST contain the context of previous chats as well if any of the previous chat was relevant."
#         if string_second_string
#         else DO_SOMETHING_PROMPT
#     )
#     if promptId != 2:
#         fast_reply_message = [
#             {"role": "system", "content": do_something_prompt + PROMPT_ID},
#             {"role": "user", "content": user_prompt + f"""\n {ADD_TO_USER_PROMPT}"""},
#         ]
#     else:
#         fast_reply_message = [
#             {"role": "system", "content": do_something_prompt + PROMPT_ID_2},
#             {"role": "user", "content": user_prompt + f"""\n {ADD_TO_USER_PROMPT}"""},
#         ]
#     print(fast_reply_message[0]["content"])
#     if promptId == 1:
#         fast_reply_tasks = [
#             asyncio.create_task(grok(fast_reply_message)),
#             asyncio.create_task(
#                 calling_aisearch_saving(
#                     convId, promptId, main_query, es_client, demoBlocked
#                 )
#             ),
#         ]

#         for coro in asyncio.as_completed(fast_reply_tasks):
#             item_ = await coro
#             if isinstance(item_, dict):
#                 fast_reply = item_
#                 if fast_reply.get("ambiguity", 0):
#                     prompt_to_show = fast_reply.get("follow_up", "")
#                 else:
#                     prompt_to_show = fast_reply.get("clear_prompt", "")
#                     if "person_location" in fast_reply:
#                         PERSON_INCLUDED_PROMPT = (
#                             fast_reply.get("person_location", 1000)
#                             if fast_reply.get("person_location", 1000)
#                             != fast_reply.get("company_location", 1000)
#                             else 1
#                         )
#     else:
#         fast_reply = await grok(fast_reply_message)
#         if fast_reply.get("ambiguity", 0):
#             prompt_to_show = fast_reply.get("follow_up", "")
#         else:
#             prompt_to_show = fast_reply.get("clear_prompt", "")
#             if "person_location" in fast_reply:
#                 PERSON_INCLUDED_PROMPT = (
#                     fast_reply.get("person_location", 1000)
#                     if fast_reply.get("person_location", 1000)
#                     != fast_reply.get("company_location", 1000)
#                     else 1
#                 )

#     async for chunk in stream_openai_text_first(prompt_to_show):
#         return_payload = {
#             "step": "text_line",
#             "text": chunk,
#             "response_id": 1,
#         }
#         yield last_converter(return_payload)

#     if fast_reply.get("ambiguity", 0):
#         results_temp = {"System Follow Up": fast_reply.get("follow_up", "")}
#         asyncio.create_task(
#             insert_into_cache_single_entity_results(
#                 convId, promptId, 1, main_query, results_temp
#             )
#         )
#         return
#     if promptId == 2:
#         if "new_information" in fast_reply and not fast_reply.get("new_information"):

#             aisearch_results = await aisearch_calling_and_retrieving(
#                 convId, promptId, main_query, main_query, es_client, demoBlocked
#             )
#             async for chunk in processing_aisearch_results(
#                 aisearch_results, 2, PERSON_INCLUDED_PROMPT
#             ):
#                 yield chunk

#             return

#     aisearch_payload = prompt_to_show if promptId > 1 else main_query
#     """ """

#     ambiguous_user_prompt = (
#         AMBIGUOUS_PROMPT_AISEARCH + user_prompt
#         if not industry_flag
#         else AMBIGUOUS_PROMPT_AISEARCH_INDUSTRY + user_prompt
#     )

#     single_entity_user_prompt = SINGLE_ENTITY_DETECTION + user_prompt_single
#     single_entity_message = [{"role": "user", "content": single_entity_user_prompt}]
#     ambiguous_message = [{"role": "user", "content": ambiguous_user_prompt}]

#     temp_tasks = (
#         [
#             asyncio.create_task(claude(single_entity_message)),
#             asyncio.create_task(
#                 claude(ambiguous_message, model="claude-3-7-sonnet-latest")
#             ),
#         ]
#         if aisearch
#         else [
#             asyncio.create_task(claude(single_entity_message)),
#             asyncio.create_task(
#                 calling_aisearch_without_saving(
#                     aisearch_payload, es_client, demoBlocked
#                 )
#             ),
#         ]
#     )

#     ambiguity = aisearch_results = None
#     if not aisearch:
#         response_entity, aisearch_results = await asyncio.gather(*temp_tasks)
#     else:
#         response_entity, ambiguity = await asyncio.gather(*temp_tasks)  # The rest

#     results = []
#     tasks = []
#     index = 1
#     count_response = 1
#     if response_entity.get("single_entities", 0):
#         plan = group_entity_steps(response_entity.get("plan", []))
#         if len(plan) < 6:
#             async for chunk in step_plans(plan, tasks, convId, promptId, main_query, index, company_keys, person_keys, count_response, es_client):
#                 yield chunk
#             return

#     if not fast_reply.get("ambiguity", 0) and not aisearch:
#         count_response = count_response + 1

#         async for chunk in processing_aisearch_results(
#             aisearch_results, 2, PERSON_INCLUDED_PROMPT
#         ):
#             yield chunk

#         results.append(
#             {
#                 "AI_Search_Results": aisearch_results,
#                 "clear_prompt": aisearch_payload,
#             }
#         )
#     elif not fast_reply.get("ambiguity", 0) and aisearch:
#         count_response += 1
#         aisearch_payload = ambiguity.get("clear_prompt", "")
#         if "attributes" in ambiguity:
#             ambiguity = context_transformation(ambiguity, demoBlocked=demoBlocked)
#         action = ambiguity.get("action", "extract")
#         filters = ambiguity.get("attributes", [])
#         indexes = ambiguity.get("indexes", [])
#         subtasks = []
#         if action.lower() == "modify":
#             if indexes and filters:

#                 context = [
#                     aisearch.get(j_ind) for j_ind in indexes if j_ind in aisearch
#                 ]
#                 if context:
#                     last_applied_filters = context[-1].get("result")

#                     return_payload = {
#                         "step": "filters",
#                         "filters_object": last_applied_filters,
#                         "filters_to_modify": filters,
#                         "response_id": count_response,
#                     }
#                     yield last_converter(return_payload)

#                     subtasks = [
#                         context_main(
#                             aisearch_payload, context, filter_, return_entity=True
#                         )
#                         for filter_ in filters
#                     ]

#         if subtasks:
#             total_modified = []
#             for coro in asyncio.as_completed(subtasks):
#                 item, entity = await coro

#                 if "location" in item and item.get("location", {}):
#                     if PERSON_INCLUDED_PROMPT < 1000:
#                         if not PERSON_INCLUDED_PROMPT:
#                             item.pop("location")

#                 if "location" in item:
#                     location_all = list(
#                         item.get("location", {}).get("filter", {}).keys()
#                     )

#                     mapped_locations = await map_locations_by_name(location_all)
#                     for key in list(item.get("location", {}).get("filter", {})):
#                         if mapped_locations.get(key):
#                             item["location"]["filter"][
#                                 mapped_locations[key]["name"]
#                             ] = item["location"]["filter"].pop(key)

#                             item["location"]["filter"][mapped_locations[key]["name"]][
#                                 "urn"
#                             ] = mapped_locations[key].get("urn", None)
#                             item["location"]["filter"][mapped_locations[key]["name"]][
#                                 "id"
#                             ] = mapped_locations[key].get("id", None)
#                         else:
#                             item["location"]["filter"].pop(key)
#                 return_payload = {
#                     "step": "filter_modification",
#                     "filters_object": item,
#                     "modified_filter": entity,
#                     "response_id": count_response,
#                 }
#                 total_modified.append(return_payload)
#                 yield last_converter(return_payload)
#             results.append(
#                 {
#                     "AI_Search_Results": total_modified,
#                     "clear_prompt": aisearch_payload,
#                 }
#             )
#         else:
#             aisearch_payload = prompt_to_show
#             subtasks = [
#                 asyncio.create_task(
#                     aisearch_main(
#                         aisearch_payload,
#                         es_client,
#                         demoBlocked=demoBlocked,
#                         return_type=True,
#                     )
#                 ),
#                 asyncio.create_task(
#                     dual_shorten_prompt(aisearch_payload, use_legacy_prompt=False)
#                 ),
#             ]


#             aisearch_results = []
#             locations_aisearch = {}
#             for coro in asyncio.as_completed(subtasks):
#                 temp_filters = await coro

#                 if isinstance(temp_filters, tuple):
#                     locations_aisearch = (
#                         temp_filters[0].pop("location")
#                         if "location" in temp_filters[0]
#                         else {}
#                     )

#                     return_payload = {
#                         "step": "filters",
#                         "filters_object": temp_filters[0],
#                         "response_id": count_response,
#                     }
#                     yield last_converter(return_payload)

#                     if locations_aisearch:
#                         if PERSON_INCLUDED_PROMPT < 1000:
#                             if not PERSON_INCLUDED_PROMPT:
#                                 locations_aisearch = {}

#                 else:
#                     return_payload = {
#                         "step": "company_filters",
#                         "filters_object": temp_filters,
#                         "response_id": count_response,
#                     }
#                     aisearch_results.append(temp_filters)

#                 yield last_converter(return_payload)

#             if locations_aisearch:
#                 location_all = list(locations_aisearch.get("filter", {}).keys())

#                 mapped_locations = await map_locations_by_name(location_all)
#                 for key in list(locations_aisearch.get("filter", {})):
#                     if mapped_locations.get(key):
#                         locations_aisearch["filter"][mapped_locations[key]["name"]] = (
#                             locations_aisearch["filter"].pop(key)
#                         )

#                         locations_aisearch["filter"][mapped_locations[key]["name"]][
#                             "id"
#                         ] = mapped_locations[key].get("id", None)
#                         locations_aisearch["filter"][mapped_locations[key]["name"]][
#                             "urn"
#                         ] = mapped_locations[key].get("urn", None)
#                     else:
#                         locations_aisearch["filter"].pop(key)

#             return_payload = {
#                 "step": "location_filter",
#                 "filters_object": {"location": locations_aisearch},
#                 "response_id": count_response,
#             }
#             yield last_converter(return_payload)
#             aisearch_results.append(temp_filters[0])

#             results.append(
#                 {
#                     "AI_Search_Results": aisearch_results,
#                     "clear_prompt": aisearch_payload,
#                 }
#             )

#     if tasks:
#         await asyncio.gather(*tasks)
#     else:
#         asyncio.create_task(
#             insert_into_cache_single_entity_results(
#                 convId, promptId, count_response, main_query, results[0]
#             )
#         )

#     return


# ADD_TO_USER_PROMPT = """
# Reason in detail with yourself the following questions:
#     1. Check if the query requests filtering on parameters our system cannot support. If our system can support, see if multiple filters can support the query or can it not be interpreted differently for multiple filters such total_working_years, tenure, etc.
#     2. Determine if a requirement could be handled by multiple different filters in our system, producing substantially different results.

# A query is ambiguous if and only if one or more of these conditions exist:
#     1. It contains requirements that could be processed through multiple different filters. If so, we need to clear the ambiguity directly from the user.
#     2. It requests filtering based on parameters our system doesn't support. In this case we need to communicate this to the user.

# If a location is mentioned:
#     1. If only companies are required, the location would refer to companies; if only people are required, the location would refer to people.
#     2. If both companies and people are mentioned in a query, and the companies referred to are specific (e.g., "Google", "FAANG") rather than generic (e.g., "companies like Google", "automotive companies"), then the location mentioned in the query should ALWAHYS be applied to the people, not the companies.
#     3. However, if both people and companies are mentioned in a query, but exact/specific companies are not required then the location reference could apply to either. In cases where non-exact companies are mentioned, if explicit terms like "living", "headquartered", or "operating" are used, we can confidently infer the intended entity. However, when vague terms like "based in", "from", or similar are used, we need to rely on the following steps for interpretation:
#         - If the location is mentioned after the person but before the company, it likely refers to the person. Location will NOT BE AMBIGUOUS in this case.
#         - If the location is mentioned after the company but before the person, it likely refers to the company. Location will NOT BE AMBIGUOUS in this case.
#         - If the location is mentioned after both the company and the person have been introduced, the reference is ambiguous, and we must ask the user for clarification.
# Remember to analyze the entire query. EXPLAIN IN DETAIL HOW YOU USED THE LOCATION STEPS ABOVE TO SATISFY THE USER'S QUERY. Ensure the clear prompt or follow up takes the whole conversation into account and mentions all the required context from the previous conversation."""


# async def retrieving_old_aisearch(conversation_id, prompt_id, constant_retrieval=False):
#     query = f"""
#         SELECT result
#         FROM single_entity_aisearch_new_temp
#         WHERE conversation_id = '{conversation_id}'
#         AND prompt_id = '{prompt_id-1}'
#         AND response_id = '1'
#         order by response_id
#     """

#     result_all = await postgres_fetch(query)
#     if not constant_retrieval:
#         if result_all:
#             result = result_all[0]
#             return result
#     else:
#         for _ in range(4):
#             if result_all:
#                 result = result_all[0]
#                 return result
#             await asyncio.sleep(3)
#             result_all = await postgres_fetch(query)
#     return None


# async def calling_aisearch_saving(convId, promptId, main_query, es_client, demoBlocked):

#     subtasks = [
#         asyncio.create_task(dual_shorten_prompt(main_query, use_legacy_prompt=False)),
#         asyncio.create_task(
#             aisearch_main(
#                 main_query,
#                 es_client,
#                 demoBlocked=demoBlocked,
#                 return_type=True,
#             )
#         ),
#     ]

#     results = await asyncio.gather(*subtasks)
#     asyncio.create_task(
#         insert_into_cache_single_entity_results(
#             convId,
#             promptId,
#             1,
#             main_query,
#             results,
#             temp=True,
#         )
#     )
#     return True


# async def aisearch_calling_and_retrieving(
#     convId, promptId, main_query, aisearch_payload, es_client, demoBlocked
# ):
#     subtasks = [
#         asyncio.create_task(
#             calling_aisearch_without_saving(aisearch_payload, es_client, demoBlocked)
#         ),
#         asyncio.create_task(
#             retrieving_old_aisearch(convId, promptId, constant_retrieval=True)
#         ),
#     ]

#     for coro in asyncio.as_completed(subtasks):
#         item = await coro
#         if item:
#             return item


""""""

# import asyncio, anthropic, json, os, re, tiktoken, httpx
# from app.core.database import postgres_fetch, postgres_insert
# from app.utils.company_generation.mapping import white_death
# from app.utils.company_generation.shorten import dual_shorten_prompt
# from app.utils.fastmode.prompts import SUMMARY_PROMPT

# from app.utils.aisearch_final.aisearch import main as aisearch_main
# from app.utils.ai_search_context.context_aisearch import context as context_main
# from sqlalchemy.sql import text
# from app.routes.dependancies import get_sqlalchemy_session_ai
# from sqlalchemy import bindparam
# from sqlalchemy.dialects.postgresql import JSONB
# from app.utils.aisearch_expansion_variants.variants import *
# from app.utils.aisearch_expansion_variants.expansion import *
# from app.utils.fastmode.prompts import PROMPT_ID_2, PROMPT_ID
# import copy
# from itertools import product
# from app.utils.fastmode.llms import grok, claude
# from app.utils.fastmode.fs_side_functions import get_profile_suggestions, ingest_profile_by_search_term, ingest_profiles_identifier, map_locations_by_name
# from app.utils.fastmode.postgres_functions import postgres_insert_custom, postgres_insert_custom_temp, insert_into_cache_single_entity_results, postgres_insert_custom_for_filters, postgres_fetch_custom, fetch_from_cache_single_entity_results, filters_modification_in_db, profile_count_modification_in_db, update_value_publicIdentifiers
# from app.utils.fastmode.expansion_variants import call_for_expansion, call_for_variants
# from app.utils.fastmode.summary import summary_text
# from helper_functions import build_all_search_strings, context_transformation, group_entity_steps, transform_context, convert_companies, last_converter, extract_generic
# from app.utils.fastmode.streaming_functions import stream_openai_text_first, sending_grok_results_back, stream_openai_text
# from app.utils.fastmode.main_functions import processing_aisearch_results, single_entity_processing, step_plans, calling_aisearch_without_saving, processing_modification, aisearch_results_first_come_first, handling_fast_reply
