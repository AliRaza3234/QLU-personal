import asyncio
from app.utils.aisearch_final.complete_aisearch import test_main as aisearch_new
from app.utils.fastmode.question_answer_utils import (
    ai_search_questions_agent,
    get_recruitment_query_questions,
)

from app.utils.fastmode.prompts import (
    PROMPT_ID,
    SUGGESTION_ACCEPTANCE_PROMPT,
    Multiple_Streams_Suggestion,
    Company_Timeline_OR_Explanation,
    Industry_Explanation,
    Job_Title_Explanation,
    Management_Level_Explanation,
    Industry_Timeline_OR_Explanation,
    Atomic_Filters_Experience_Explanation,
    Atomic_Filters_Role_Tenure_Explanation,
    Atomic_Filters_Company_Tenure_Explanation,
    Strict_Match_Explanation,
    Current_Timeline_Company_Explanation,
    Current_Timeline_Industry_Explanation,
    Industry_Breakdown_Prompt,
    Pureplay_Prompt,
    General_Ambiguity_Prompt,
    Industry_Pureplay_Both_Prompt,
    General_Ambiguity_ONLY_Prompt,
    PURE_PLAY_QUESTION,
    WRITING_THE_FIRST_FING_LINE,
    Proper_Phrasing_Prompt,
    PUREPLAY_DO_NOT_REPEAT_QUESTION_GUIDELINES,
    LOCATIONS_VERIFIER_AGENT,
    KEYWORD_WITH_TITLE_PROMPT,
    SINGLE_ENTITY_DETECTION,
)
from app.utils.fastmode.question_answer_utils import (
    and_timeline_ambiguity_detection_agent,
    timeline_selection_analysis_agent,
    generate_reply_agent,
    pre_questions_coro,
    new_industry_question_agent,
    new_pureplay_question_agent,
)
from app.utils.fastmode.llms import grok, grok_rewritten, claude, claude_with_system
from app.utils.fastmode.postgres_functions import (
    insert_into_cache_single_entity_results,
    fetch_from_cache_single_entity_results,
    filters_modification_in_db,
    profile_count_modification_in_db,
    update_value_publicIdentifiers,
    possible_suggestion_filters,
    possible_suggestion_filters_companyTimeline,
)
from app.utils.fastmode.expansion_variants import call_for_expansion, call_for_variants
from app.utils.fastmode.helper_functions import last_converter
from app.utils.fastmode.main_functions import (
    processing_aisearch_results,
    processing_aisearch_results_suggestions,
    single_entity_processing,
    calling_aisearch_without_saving,
    processing_modification,
    new_aisearch_results,
    handling_fast_reply,
    suggestions_preparations,
)
from app.utils.fastmode.suggestions import suggestions
from app.utils.fastmode.shared_state import ASYNC_TASKS
from app.utils.fastmode.streaming_functions import (
    stream_openai_text,
    sending_grok_results_back,
)
import random

modification_keys = {
    "filters_compstream": Multiple_Streams_Suggestion,
    "industry_combo_filters": Industry_Explanation,
    "management_level_combo_filters": Management_Level_Explanation,
    "titles_management_levels_combo_filters": Job_Title_Explanation,
    "companies_timeline_OR_combo_filters": Company_Timeline_OR_Explanation,
    "strict_match": Strict_Match_Explanation,
}


async def no_filter_results_suggestions(prompt, convId, promptId, respId):

    suggestions = [
        "Let me know how I can refine your search to better match what you're looking for.",
        "Need me to adjust the search? Just let me know what you'd like to focus on or change.",
        "Let me know if there's another way you'd like me to refine your search.",
        "Let me know if there's anything else I can help you with.",
    ]
    # return
    sum_of_text = ""
    async for chunk in stream_openai_text(random.choice(suggestions)):
        return_payload = {
            "step": "text_line",
            "text": chunk,
            "response_id": respId + 2,
        }
        yield last_converter(return_payload)
        sum_of_text += chunk

    asyncio.create_task(
        insert_into_cache_single_entity_results(
            convId, promptId, respId + 2, prompt, {"System Follow Up": sum_of_text}
        )
    )
    return


async def handling_grok_replies(
    item,
    last_suggestion,
    convId,
    promptId,
    main_query,
    count_response,
    es_client,
    already_given_suggestions,
    full_context,
    demoBlocked,
):
    if (
        item.get("action", 0)
        and item.get("action", 0) == 1
        and last_suggestion.get("promptId")
    ):
        filters_to_suggest = await possible_suggestion_filters(
            convId, last_suggestion.get("promptId")
        )
        if filters_to_suggest:
            return_payload = {
                "step": "text_line",
                "text": last_suggestion.get("updated_filters_string", ""),
                "response_id": count_response,
            }
            yield last_converter(return_payload)
            count_response += 1

            async for chunk in processing_aisearch_results_suggestions(
                filters_to_suggest,
                count_response,
                last_suggestion.get("suggestion_text", ""),
                convId,
                promptId,
                special_handling=False,
            ):
                yield chunk

            results = [
                {
                    "AI_Search_Results": filters_to_suggest,
                    "clear_prompt": last_suggestion.get("suggestion_text", ""),
                }
            ]
            asyncio.create_task(
                insert_into_cache_single_entity_results(
                    convId, promptId, count_response, main_query, results[0]
                )
            )
            asyncio.create_task(
                suggestions_preparations(
                    main_query,
                    convId,
                    promptId,
                    es_client,
                    already_given_suggestions,
                    demoBlocked=demoBlocked,
                    context=full_context,
                )
            )
            return
    elif not item.get("action"):
        async for chunk in no_filter_results_suggestions(
            main_query, convId, promptId, count_response
        ):
            yield chunk

        return
    elif item.get("action") and item.get("action", 0) == 3:
        sum_of_text = ""
        async for chunk in stream_openai_text(item.get("explanation", "")):
            return_payload = {
                "step": "text_line",
                "text": chunk,
                "response_id": count_response,
            }
            yield last_converter(return_payload)
            sum_of_text += chunk

        results = [{"Explanation": sum_of_text}]
        asyncio.create_task(
            insert_into_cache_single_entity_results(
                convId, promptId, count_response, main_query, results[0]
            )
        )
        return

    yield "Interesting By Arsal"
    return


def build_suggestion_explanation(approach, modified_filters, modification_keys):
    explanation = ""
    if approach in modification_keys:
        explanation = modification_keys.get(approach)
        if approach == "exp_tenures_combo_filters":
            explanation = explanation.replace("[]", modified_filters)
    else:
        if approach == "current_timeline":
            if "Company" in modified_filters:
                explanation = f"{Company_Timeline_OR_Explanation}"
            if "Industry" in modified_filters:
                explanation += f"{Industry_Timeline_OR_Explanation}"
        elif approach == "industries_companies_timeline_OR_combo_filters":
            if "Company" in modified_filters:
                explanation = f"{Current_Timeline_Company_Explanation}"
            if "Industry" in modified_filters:
                explanation += f"{Current_Timeline_Industry_Explanation}"
        elif approach == "exp_tenures_combo_filters":
            if "Experience" in modified_filters:
                explanation = Atomic_Filters_Experience_Explanation
            if "Company Tenure" in modified_filters:
                explanation += Atomic_Filters_Role_Tenure_Explanation
            if "Role Tenure" in modified_filters:
                explanation += Atomic_Filters_Company_Tenure_Explanation

    return explanation


async def _await_next(iterator):
    return await iterator.__anext__()


def _as_task(iterator):
    return asyncio.create_task(_await_next(iterator))


def random_place_holder_statement():
    suggestions = [
        "_Understood. Reviewing to determine the most relevant next step._",
        "_Analyzing your request to surface the most appropriate result._",
        "_Assessing the details to guide the response accordingly._",
        "_Reviewing the input to ensure the response aligns with your intent._",
        "_Taking a moment to evaluate what best addresses your request._",
        "_Interpreting the context to prepare the most useful output._",
        "_Looking into the specifics to deliver the right kind of response._",
        "_Processing the information to tailor the next step effectively._",
    ]
    return random.choice(suggestions)


async def writing_the_f_thing(item, already_shown_string, last=False):
    last = False
    formatting_instructions = """
### Formatting Instructions
1.  When writing the question, you need to make sure that the text is in markdown with proper indentation and numbered bullet points.
2.  Preserve the original phrasing of all questions and text. Do not reword, add, or delete anything from the content of the questions.
3.  If it is a single question, and nothing is currently in already_shown_string, then you need to write the question in a single numbered bullet point starting with 1.
4.  If there is already a numbered list in already_shown_string, then you need to write the question in a new numbered bullet point starting with the next number in the sequence.
5.  Numbering and Structure:
    * Use a standard numbered list format (`1.`, `2.`, `3.`, etc.) for all primary questions.
    * If a question in the original text has its own bullet point (`*`, `-`) or number, remove it before placing the question into the new list.
    * Ensure the final list flows in a single ascending sequence of numbered markdown bullet points.
6.  **Sub-Questions:** If a primary question contains a list of sub-questions or items, format them as an indented list directly below it. And make sure that each sub-question is properly indented with 4 spaces and is on a new line in proper markdown format.
7.  **Final Check:** The output must be clean markdown with proper indentation and proper spacing for readability."""
    if not item:
        return ""

    if not last:
        user_prompt = f"<question_to_ask>\n{item}\n</question_to_ask>\n<already_shown_text>\n{already_shown_string}\n</already_shown_text><formatting instructions>{formatting_instructions}</formatting instructions>"
    else:
        user_prompt = f"This is the last question or set of questions. Correctly identify the last question.\n<question_to_ask>\n{item}\n</question_to_ask>\n<already_shown_text>\n{already_shown_string}\n</already_shown_text><formatting instructions>{formatting_instructions}</formatting instructions>"

    messages = [
        {"role": "system", "content": WRITING_THE_FIRST_FING_LINE},
        {"role": "user", "content": user_prompt},
    ]

    rewritten_question = await grok_rewritten(messages)
    # print("-"*50)
    # print("already_shown_string\n", already_shown_string)
    # print("\nItem:", item)
    # print("\nRewritten_Query\n", rewritten_question)
    # print("-"*50)
    return rewritten_question


async def company_timeline_confirmation(
    company_timeline_task, main_query, convId, promptId, count_response
):
    company_timeline_ambiguity = await company_timeline_task

    if (
        not company_timeline_ambiguity.get("modifications", False)
        and company_timeline_ambiguity.get("selected_timeline", "").lower()
        != "not_selected"
    ):
        filters_to_return = await possible_suggestion_filters_companyTimeline(
            convId, promptId
        )

        if filters_to_return:
            if company_timeline_ambiguity.get("selected_timeline", "").lower() != "and":
                if filters_to_return.get("companies", {}).get(
                    "current"
                ) and filters_to_return.get("companies", {}).get("past"):
                    filters_to_return["companies"]["current"][0] += (
                        ", " + filters_to_return["companies"]["past"][0]
                    )
                    filters_to_return["companies"]["past"] = []
                    filters_to_return["companies"]["timeline"] = (
                        company_timeline_ambiguity.get("selected_timeline")
                    )

            async for chunk in new_aisearch_results(
                main_query,
                filters_to_return,
                count_response,
                convId,
                promptId,
                main_query,
            ):
                yield chunk
            return

    elif (
        company_timeline_ambiguity.get("modifications", False)
        and company_timeline_ambiguity.get("selected_timeline", "").lower()
        != "not_selected"
    ):
        if company_timeline_ambiguity.get("selected_timeline", "").lower() == "current":
            add_to_clear_prompt = f"""<Company_Timeline_Information>Company's Timeline **must be {company_timeline_ambiguity.get("selected_timeline", "")}**, all mentioned industries should be included in current_prompt</Company_Timeline_Information>"""
        elif "or" in company_timeline_ambiguity.get("selected_timeline", "").lower():
            add_to_clear_prompt = f"""<Company_Timeline_Information>Company's Timeline **must be {company_timeline_ambiguity.get("selected_timeline", "")}**, all mentioned industries should be included in either_prompt</Company_Timeline_Information>"""
        elif company_timeline_ambiguity.get("selected_timeline", "").lower() == "past":
            add_to_clear_prompt = f"""<Company_Timeline_Information>Company's Timeline **must be {company_timeline_ambiguity.get("selected_timeline", "")}**, all mentioned industries should be included in past_prompt</Company_Timeline_Information>"""
        elif company_timeline_ambiguity.get("selected_timeline", "").lower() == "and":
            add_to_clear_prompt = f"""<Company_Timeline_Information>Company's Timeline **must be {company_timeline_ambiguity.get("selected_timeline", "")}**, past_prompt and current_prompt both required</Company_Timeline_Information>"""
        yield {"add_to_clear_prompt": add_to_clear_prompt}
        return

    yield ""
    return


async def first_prompt_aisearch_grok(
    main_query,
    aisearch,
    convId,
    promptId,
    fast_reply_task,
    single_entity_message,
    modification_detector,
    suggestion_acceptance,
    full_context,
    last_suggestion,
    demoBlocked,
    last_aisearch,
    es_client,
    qdrant_client,
    tasks,
    index,
    company_keys,
    person_keys,
    count_response,
    already_given_suggestions,
    clarification,
    pure_play_or_not_task,
):
    pre_question_coro_task = asyncio.create_task(
        pre_questions_coro(full_context, clarification)
    )

    industry_question_task = asyncio.create_task(
        new_industry_question_agent(pre_question_coro_task)
    )

    pureplay_question_task = asyncio.create_task(
        new_pureplay_question_agent(pre_question_coro_task)
    )

    get_recruitement_task = asyncio.create_task(
        get_recruitment_query_questions(full_context, clarification)
    )

    suggestion_acceptance_task = []
    if suggestion_acceptance:
        suggestion_acceptance_task = asyncio.create_task(grok(suggestion_acceptance))

    first_task = [
        fast_reply_task,
        industry_question_task,
        pureplay_question_task,
        get_recruitement_task,
    ]

    second_task = [asyncio.create_task(claude(single_entity_message, checking=False))]
    if not last_aisearch:

        asyncio.create_task(
            suggestions_preparations(
                main_query,
                convId,
                promptId,
                es_client,
                already_given_suggestions,
                demoBlocked=demoBlocked,
            )
        )
        third_task = asyncio.create_task(
            aisearch_new(main_query, es_client, qdrant_client, demoBlocked=demoBlocked)
        )
        timeline_ambiguity_task = asyncio.create_task(
            and_timeline_ambiguity_detection_agent(full_context)
        )
    else:
        third_task = [
            asyncio.create_task(
                claude(
                    modification_detector,
                    model="claude-sonnet-4-20250514",
                    checking=False,
                )
            )
        ]

    if suggestion_acceptance:
        item_suggested = await suggestion_acceptance_task
        if isinstance(item_suggested, dict) and "action" in item_suggested:
            async for chunk in handling_grok_replies(
                item_suggested,
                last_suggestion,
                convId,
                promptId,
                main_query,
                count_response,
                es_client,
                already_given_suggestions,
                full_context,
                demoBlocked,
            ):
                if chunk != "Interesting By Arsal":
                    yield chunk

            if chunk != "Interesting By Arsal":
                return

    count = 1
    sum_of_first_text = ""
    break_flag = False
    last = False
    question_agent_flag = False
    industry_recruitment_question_task = None
    # possible_place_holder = random_place_holder_statement()
    # await asyncio.sleep(2)
    # async for chunk in stream_openai_text(possible_place_holder):
    #     return_payload = {
    #         "step": "text_line",
    #         "text": chunk,
    #         "response_id": count_response,
    #     }
    #     yield last_converter(return_payload)
    # sum_of_first_text += chunk
    count_response += 1
    questions_to_ask = []
    for coro in asyncio.as_completed(first_task):
        item = await coro
        if isinstance(item, dict) and "ambiguity" in item:
            fast_reply = item
            if item.get("ambiguity"):
                last = True if count == 3 and break_flag else False
                ambiguous_task = asyncio.create_task(
                    writing_the_f_thing(
                        fast_reply.get("follow_up"), sum_of_first_text, last
                    )
                )
            else:
                prompt_to_show = fast_reply.get("clear_prompt")
                aisearch_payload = prompt_to_show
                # await asyncio.sleep(3)

            if item.get("ambiguity"):
                rewritten_question = await ambiguous_task
                if rewritten_question:
                    break_flag = True
                    async for chunk in stream_openai_text(rewritten_question):
                        return_payload = {
                            "step": "text_line",
                            "text": chunk,
                            "response_id": count_response,
                        }
                        yield last_converter(return_payload)
                        sum_of_first_text += chunk

                    count_response += 1
                questions_to_ask.append("Ambiguity")

        elif isinstance(item, dict) and "question" in item:
            question_agent_flag = True
            if item.get("question"):
                question_industry = item.get("industry_question", "")
                question_pureplay = item.get("pureplay_question", "")

                if question_industry:
                    question_agent_flag = False
                elif not question_industry and industry_recruitment_question_task:
                    rewritten_question = await industry_recruitment_question_task
                    if rewritten_question:
                        break_flag = True
                        async for chunk in stream_openai_text(rewritten_question):
                            return_payload = {
                                "step": "text_line",
                                "text": chunk,
                                "response_id": count_response,
                            }
                            yield last_converter(return_payload)
                            sum_of_first_text += chunk
                        count_response += 1
                        questions_to_ask.append("Industry")

                question_industry_task = []
                if question_pureplay and isinstance(question_pureplay, str):
                    last = True if count == 3 and break_flag else False
                    rewritten_question = await writing_the_f_thing(
                        question_pureplay, sum_of_first_text, last
                    )
                    if rewritten_question:
                        if question_industry:
                            question_industry_task = asyncio.create_task(
                                writing_the_f_thing(
                                    question_industry,
                                    sum_of_first_text + f"{rewritten_question}",
                                    last,
                                )
                            )

                        break_flag = True
                        async for chunk in stream_openai_text(rewritten_question):
                            return_payload = {
                                "step": "text_line",
                                "text": chunk,
                                "response_id": count_response,
                            }
                            yield last_converter(return_payload)
                            sum_of_first_text += chunk
                        count_response += 1
                        questions_to_ask.append("Pure Play")

                if question_industry and isinstance(question_industry, str):
                    if question_industry_task:
                        rewritten_question = await question_industry_task
                    else:
                        rewritten_question = await writing_the_f_thing(
                            question_industry, sum_of_first_text, last
                        )
                    if rewritten_question:
                        break_flag = True
                        async for chunk in stream_openai_text(rewritten_question):
                            return_payload = {
                                "step": "text_line",
                                "text": chunk,
                                "response_id": count_response,
                            }
                            yield last_converter(return_payload)
                            sum_of_first_text += chunk
                        count_response += 1
                        questions_to_ask.append("Industry")

        elif (
            isinstance(item, dict)
            and "recruitment_question" in item
            and item.get("recruitment_question")
        ):
            recruitment_questions_return_to_ask = list(item.keys())
            recruitment_questions_return_to_ask.remove("recruitment_question")
            awaited_question_task = None

            for index_number, key in enumerate(recruitment_questions_return_to_ask):
                if key == "recruitment_question":
                    continue
                if key == "industry" and not question_agent_flag:
                    industry_recruitment_question_task = asyncio.create_task(
                        writing_the_f_thing(item.get(key, ""), sum_of_first_text, last)
                    )
                    continue

                # recruitment_questions_return_task.append(asyncio.create_task(
                #         writing_the_f_thing(
                #             value,
                #             sum_of_first_text,
                #             last,
                #         )
                #     )
                # )

                if not awaited_question_task:
                    rewritten_question = await writing_the_f_thing(
                        item.get(key), sum_of_first_text, False
                    )
                else:
                    rewritten_question = await awaited_question_task
                    awaited_question_task = None

                if rewritten_question:
                    if (
                        index_number + 1 < len(recruitment_questions_return_to_ask)
                    ) and (
                        recruitment_questions_return_to_ask[index_number + 1]
                        != "industry"
                        or question_agent_flag
                    ):
                        awaited_question_task = asyncio.create_task(
                            writing_the_f_thing(
                                item.get(
                                    recruitment_questions_return_to_ask[
                                        index_number + 1
                                    ]
                                ),
                                sum_of_first_text + f"{rewritten_question}",
                                last,
                            )
                        )

                    break_flag = True
                    async for chunk in stream_openai_text(rewritten_question):
                        return_payload = {
                            "step": "text_line",
                            "text": chunk,
                            "response_id": count_response,
                        }
                        yield last_converter(return_payload)
                        sum_of_first_text += chunk
                    count_response += 1
                    questions_to_ask.append(key)

        elif isinstance(item, str):
            pure_play_string = item
            if pure_play_string and isinstance(pure_play_string, str):
                last = True if count == 3 and break_flag else False
                rewritten_question = await writing_the_f_thing(
                    pure_play_string, sum_of_first_text, last
                )
                if rewritten_question:
                    break_flag = True
                    async for chunk in stream_openai_text(rewritten_question):
                        return_payload = {
                            "step": "text_line",
                            "text": chunk,
                            "response_id": count_response,
                        }
                        yield last_converter(return_payload)
                        sum_of_first_text += chunk
                    count_response += 1
                    questions_to_ask.append("Pure Play")

        count += 1

    if sum_of_first_text:
        asyncio.create_task(
            insert_into_cache_single_entity_results(
                convId,
                promptId,
                1,
                main_query,
                {"System Follow Up": sum_of_first_text, "questions": questions_to_ask},
            )
        )

    # if break_flag:
    #     return

    if fast_reply.get("clear_prompt", ""):
        return_payload = {
            "step": "rewritten_prompt",
            "text": fast_reply,
            "response_id": 1,
        }
        yield last_converter(return_payload)

    if not break_flag:
        async for chunk in handling_fast_reply(fast_reply, count_response):
            yield chunk

    count_response += 1

    ambiguity_clearing = await asyncio.gather(*second_task)
    response_entity = ambiguity_clearing[0]
    clear_prompt_shown = False

    if not break_flag:
        if response_entity.get("single_entity", 0):
            # async for chunk in handling_fast_reply(fast_reply, count_response):
            #     yield chunk
            # count_response += 1

            async for chunk in single_entity_processing(
                response_entity,
                tasks,
                convId,
                promptId,
                main_query,
                count_response,
                company_keys,
                person_keys,
                count_response,
                es_client,
            ):
                yield chunk
            return

    if not last_aisearch:
        company_timeline_ambiguity = await timeline_ambiguity_task
        # if (
        #     "ambiguity" in company_timeline_ambiguity
        #     and not company_timeline_ambiguity.get("ambiguity", 0)
        # ):
        #     if not break_flag:
        #         clear_prompt_shown = True
        #         async for chunk in handling_fast_reply(fast_reply, count_response):
        #             yield chunk
        #         count_response += 1
        #     else:
        #         return

        temp_filters = await third_task
        if "companies" in temp_filters and "ambiguity" in company_timeline_ambiguity:
            company_dict = temp_filters.get("companies", {})
            if "and" in company_dict.get(
                "timeline", ""
            ).lower() and company_timeline_ambiguity.get("ambiguity", 0):
                and_question = f"""o you want only those people who are currently in the **{company_dict.get("current", [])[0]}** and previously used to be in **{company_dict.get("past", [])[0]}**?"""
                if break_flag:
                    and_question = "- Lastly, d" + and_question
                else:
                    and_question = "- D" + and_question

                rewritten_question = await asyncio.create_task(
                    writing_the_f_thing(and_question, sum_of_first_text, True)
                )
                if rewritten_question:
                    break_flag = True
                    async for chunk in stream_openai_text(rewritten_question):
                        return_payload = {
                            "step": "text_line",
                            "text": chunk,
                            "response_id": count_response,
                        }
                        yield last_converter(return_payload)
                        sum_of_first_text += chunk
                asyncio.create_task(
                    insert_into_cache_single_entity_results(
                        convId,
                        promptId,
                        count_response,
                        main_query,
                        {"System Follow Up": and_question, "and_question": True},
                    )
                )
                asyncio.create_task(
                    insert_into_cache_single_entity_results(
                        convId,
                        promptId,
                        -122,
                        main_query,
                        {"selected_filters": temp_filters},
                        temp=True,
                    )
                )
                return
        if not break_flag:
            # if fast_reply and not clear_prompt_shown:
            #     async for chunk in handling_fast_reply(fast_reply, count_response):
            #         yield chunk
            #     count_response += 1
            async for chunk in new_aisearch_results(
                main_query, temp_filters, count_response, convId, promptId, main_query
            ):
                yield chunk
            return
    else:
        modification_result = await asyncio.gather(*third_task)
        ambiguity = modification_result[0]

        temp = ""
        async for chunk in processing_modification(
            count_response,
            ambiguity,
            demoBlocked,
            aisearch,
            convId,
            promptId,
            main_query,
            fast_reply,
        ):
            if chunk != "None" and not break_flag:
                yield chunk
                temp += chunk

        if chunk and chunk != "None" and not break_flag:
            asyncio.create_task(
                suggestions_preparations(
                    main_query,
                    convId,
                    promptId,
                    es_client,
                    already_given_suggestions,
                    demoBlocked=demoBlocked,
                    context=full_context,
                )
            )
            return
        if chunk == "None":
            if ambiguity and ambiguity.get("clear_prompt", ""):
                aisearch_payload = ambiguity.get("clear_prompt", "")
            else:
                aisearch_payload = prompt_to_show
            asyncio.create_task(
                suggestions_preparations(
                    aisearch_payload,
                    convId,
                    promptId,
                    es_client,
                    already_given_suggestions,
                    demoBlocked=demoBlocked,
                )
            )
            subtasks = asyncio.create_task(
                aisearch_new(
                    main_query, es_client, qdrant_client, demoBlocked=demoBlocked
                )
            )
            timeline_ambiguity_task = asyncio.create_task(
                and_timeline_ambiguity_detection_agent(full_context)
            )
            company_timeline_ambiguity = await timeline_ambiguity_task
            # if (
            #     "ambiguity" in company_timeline_ambiguity
            #     and not company_timeline_ambiguity.get("ambiguity", 0)
            # ):
            #     if not break_flag:
            #         clear_prompt_shown = True
            #         async for chunk in handling_fast_reply(fast_reply, count_response):
            #             yield chunk
            #         count_response += 1
            #     else:
            #         return

            temp_filters = await subtasks

            if (
                "companies" in temp_filters
                and "ambiguity" in company_timeline_ambiguity
            ):
                company_dict = temp_filters.get("companies", {})
                if "and" in company_dict.get(
                    "timeline", ""
                ).lower() and company_timeline_ambiguity.get("ambiguity", 0):
                    and_question = f"""o you want only those people who are currently in the **{company_dict.get("current", [])[0]}** and previously used to be in **{company_dict.get("past", [])[0]}**?"""
                    if break_flag:
                        and_question = "- Lastly, d" + and_question
                    else:
                        and_question = "- D" + and_question
                    rewritten_question = await asyncio.create_task(
                        writing_the_f_thing(and_question, sum_of_first_text, True)
                    )
                    if rewritten_question:
                        break_flag = True
                        async for chunk in stream_openai_text(rewritten_question):
                            return_payload = {
                                "step": "text_line",
                                "text": chunk,
                                "response_id": count_response,
                            }
                            yield last_converter(return_payload)
                            sum_of_first_text += chunk
                    asyncio.create_task(
                        insert_into_cache_single_entity_results(
                            convId,
                            promptId,
                            count_response,
                            main_query,
                            {"System Follow Up": and_question, "and_question": True},
                        )
                    )
                    asyncio.create_task(
                        insert_into_cache_single_entity_results(
                            convId,
                            promptId,
                            -122,
                            main_query,
                            {"selected_filters": temp_filters},
                            temp=True,
                        )
                    )
                    return
            if not break_flag:
                # if fast_reply and not clear_prompt_shown:
                #     async for chunk in handling_fast_reply(fast_reply, count_response):
                #         yield chunk
                #     count_response += 1
                async for chunk in new_aisearch_results(
                    main_query,
                    temp_filters,
                    count_response,
                    convId,
                    promptId,
                    main_query,
                ):
                    yield chunk
                return


async def main(
    convId,
    promptId,
    main_query,
    visible_profiles,
    es_client,
    qdrant_client,
    demoBlocked=False,
):

    if demoBlocked:
        from app.utils.fastmode.prompts_no_demo import (
            AMBIGUOUS_PROMPT_AISEARCH,
            AMBIGUOUS_PROMPT_AISEARCH_INDUSTRY,
        )
    else:
        from app.utils.fastmode.prompts import (
            AMBIGUOUS_PROMPT_AISEARCH,
            AMBIGUOUS_PROMPT_AISEARCH_INDUSTRY,
        )

    string_second_string = ""
    aisearch = None
    industry_flag = False
    last_aisearch = None
    last_suggestion = {}
    modification_user_prompt = ""
    already_suggested_list = []
    clarification = False
    questions = []
    company_question = False
    ACTUAL_NEW_PURE_PLAY_SYSTEM_PROMPT = PURE_PLAY_QUESTION
    if promptId > 1:
        (
            string_second_string,
            aisearch,
            industry_flag,
            last_aisearch,
            last_suggestion,
            clarification,
            questions,
            company_question,
            already_suggested_list,
        ) = await fetch_from_cache_single_entity_results(convId, promptId, demoBlocked)

    fast_reply_task = asyncio.create_task(
        generate_reply_agent(
            main_query, string_second_string, last_suggestion, questions, demoBlocked
        )
    )
    if string_second_string:
        ACTUAL_NEW_PURE_PLAY_SYSTEM_PROMPT += PUREPLAY_DO_NOT_REPEAT_QUESTION_GUIDELINES
        user_prompt = f"""<Whole_Conversation>\n{string_second_string}<Last_Query>\n{main_query}\n</Last_Query>\n<Whole_Conversation>\n Always take into account the full context of the conversation, including all previous queries, results, and system-generated follow-ups. If the new query is a response to a previous follow-up by another agent, treat it as a continuation and construct the new clear prompt using all relevant context. Do not repeat questions that have already been asked, especially those regarding ambiguity — if the user hasn’t responded to a previous ambiguity-related question, assume ambiguity=0 and proceed by forming a clear prompt that closely mirrors the user’s wording across the conversation; however if the user asks for explanation then rephrase in simple words what was asked before. Think logically about how the latest input relates to earlier ones, and only drop context if it’s certain the new message is unrelated. Since the final clear prompt drives the backend results, it **must fully reflect the conversation’s evolving intent**. Review the **latest query for any new information**. If **this new information** makes it essential to clarify career path timing or to define an acronym, you should ask for those specific details. Otherwise, do not ask.

        """
        modification_user_prompt = f"""<Whole_Conversation>\n{string_second_string}<Last_Query>\n{main_query}\n</Last_Query>\n<Whole_Conversation>\n Consider the previous queries and their results as well. Consider that system follow ups were asked to the user by your brother agent and take them into account as well, unless the user is introducing something completely new.
        """

        if last_suggestion:
            modification_user_prompt += """If the suggestions agent had asked something before and the user has replied to them, take it into account as well based on what the suggestion was."""
        else:
            user_prompt += """If the user asks what refining the search means, can follow_up with them how they'd like to narrow or adjust the search."""

        if industry_flag:
            modification_user_prompt += """ If the user had been suggested adding industries which would fit as an exact industry keyword then only industry attribute would be required with instructions to add the exact mentioned keywords, but if the user doesn't mean an exact industry keyword then company should be called. As in if the suggestion was to add the related industries 'manufacturing', 'marketting' then the instruction should be to "Add the industry keywords: 'manufacturing' and 'marketting' as industries only" and ***industry** attribute should be called, **not** the company_product filter (In such cases, instruction should be to add only the keywords required by the user and not generate synonyms).
            """
        user_prompt_single = f"""<Whole_Conversation>\n{string_second_string}<Last_Query>\n{main_query}\n</Last_Query>\n<Whole_Conversation>\n Consider ALL the previous queries and their results as well. Consider that system follow ups were asked to the user by your brother agent; if the user is clarifying something from before then you must take the WHOLE relevant conversation into account. Take a deep breath and reason logically about how and whether the new prompt relates to the previous ones (can also use identifiers if you know of them)."""
    else:
        user_prompt = f"""<User_Prompt>\n{main_query}\n</User_Prompt>"""
        user_prompt_single = user_prompt
        modification_user_prompt = user_prompt

    person_keys = {
        "summary": "summary",
        "experience": "experience",
        "information": "contact",
        "pay_progression": "pay",
        "similar_profiles": "similar_profiles",
        "education": "education",
        "skills": "skills",
        "industries": "industries",
    }
    company_keys = {
        "summary": "summary",
        "financials": "financials",
        "m&a": "m&a",
        "leadership": "leadership",
        "competitors": "competitors",
        "reports": "reports",
        "business_units": "business_units",
        "news": "news",
        "products": "products",
    }

    full_context = f"""<Whole_Conversation>\n{string_second_string}<Last_Query>\n{main_query}\n</Last_Query>\n<Whole_Conversation>\n"""
    if last_suggestion:
        approach = already_suggested_list[-1]
        modified_filters = last_suggestion.get("modified_filters", [])
        explanation = build_suggestion_explanation(
            approach, modified_filters, modification_keys
        )

        suggestion_acceptance = [
            {"role": "system", "content": f"{SUGGESTION_ACCEPTANCE_PROMPT}"},
            {
                "role": "user",
                "content": f"""Context: {full_context}\nLast_Suggestion: {last_suggestion.get("suggestion", "")}\nSuggestion's explanation:{explanation}""",
            },
        ]
    else:
        suggestion_acceptance = None

    company_timeline_task = []
    if company_question:
        company_timeline_task = asyncio.create_task(
            timeline_selection_analysis_agent(full_context)
        )

    MODIFICATION_FOLLOW_UP_SYSTEM_PROMPT = (
        AMBIGUOUS_PROMPT_AISEARCH
        if not industry_flag
        else AMBIGUOUS_PROMPT_AISEARCH_INDUSTRY
    )

    single_entity_user_prompt = (
        SINGLE_ENTITY_DETECTION
        + user_prompt_single
        + (
            f"""<Profiles_User_Is_Seeing>\n{visible_profiles}\n</Profiles_User_Is_Seeing>"""
            if visible_profiles
            else ""
        )
    )
    single_entity_message = [{"role": "user", "content": single_entity_user_prompt}]
    modification_detector = [
        {"role": "system", "content": MODIFICATION_FOLLOW_UP_SYSTEM_PROMPT},
        {"role": "user", "content": modification_user_prompt},
    ]
    pure_play_message = [{"role": "user", "content": full_context}]
    pure_play_or_not_task = asyncio.create_task(
        claude_with_system(
            pure_play_message,
            model="claude-sonnet-4-20250514",
            SYSTEM_PROMPT=ACTUAL_NEW_PURE_PLAY_SYSTEM_PROMPT,
        )
    )

    results = []
    tasks = []
    index = 1
    count_response = 1
    if promptId == 1 or last_aisearch:
        async for chunk in first_prompt_aisearch_grok(
            main_query,
            aisearch,
            convId,
            promptId,
            fast_reply_task,
            single_entity_message,
            modification_detector,
            suggestion_acceptance,
            full_context,
            last_suggestion,
            demoBlocked,
            last_aisearch,
            es_client,
            qdrant_client,
            tasks,
            index,
            company_keys,
            person_keys,
            count_response,
            already_suggested_list,
            clarification,
            pure_play_or_not_task,
        ):
            yield chunk

        return

    if aisearch:
        temp_tasks = [
            asyncio.create_task(claude(single_entity_message, checking=False)),
            asyncio.create_task(
                claude(
                    modification_detector,
                    model="claude-sonnet-4-20250514",
                    checking=False,
                )
            ),
        ]

    pre_question_coro_task = asyncio.create_task(
        pre_questions_coro(full_context, clarification)
    )

    industry_question_task = asyncio.create_task(
        new_industry_question_agent(pre_question_coro_task)
    )
    pureplay_question_task = asyncio.create_task(
        new_pureplay_question_agent(pre_question_coro_task)
    )

    get_recruitement_task = asyncio.create_task(
        get_recruitment_query_questions(full_context, clarification)
    )

    suggestion_acceptance_task = []
    if suggestion_acceptance:
        suggestion_acceptance_task = asyncio.create_task(grok(suggestion_acceptance))

    first_task = [
        fast_reply_task,
        industry_question_task,
        pureplay_question_task,
        get_recruitement_task,
    ]

    if suggestion_acceptance:
        item_suggested = await suggestion_acceptance_task
        if isinstance(item_suggested, dict) and "action" in item_suggested:
            async for chunk in handling_grok_replies(
                item_suggested,
                last_suggestion,
                convId,
                promptId,
                main_query,
                count_response,
                es_client,
                already_suggested_list,
                full_context,
                demoBlocked,
            ):
                if chunk != "Interesting By Arsal":
                    yield chunk

            if chunk != "Interesting By Arsal":
                return

    count = 1
    sum_of_first_text = ""
    break_flag = False

    # possible_place_holder = random_place_holder_statement()
    # if not company_timeline_task:
    #     await asyncio.sleep(2)
    # async for chunk in stream_openai_text(possible_place_holder):
    #     return_payload = {
    #         "step": "text_line",
    #         "text": chunk,
    #         "response_id": count_response,
    #     }
    #     yield last_converter(return_payload)

    count_response += 1
    add_to_clear_prompt = ""
    if company_timeline_task:
        async for chunk_comp in company_timeline_confirmation(
            company_timeline_task, main_query, convId, promptId, count_response
        ):
            if chunk_comp and "add_to_clear_prompt" not in chunk_comp:
                yield chunk_comp

        if chunk_comp and "add_to_clear_prompt" not in chunk_comp:
            return
        elif (
            chunk_comp
            and isinstance(chunk_comp, dict)
            and "add_to_clear_prompt" in chunk_comp
        ):
            add_to_clear_prompt = chunk_comp.get("add_to_clear_prompt", "")
            count_response += 1

    count_response += 1
    questions_to_ask = []
    last = False
    question_agent_flag = False
    industry_recruitment_question_task = None
    for coro in asyncio.as_completed(first_task):
        item = await coro
        if isinstance(item, dict) and "ambiguity" in item:
            fast_reply = item
            if item.get("ambiguity"):
                last = True if count == 3 and break_flag else False
                ambiguous_task = asyncio.create_task(
                    writing_the_f_thing(
                        fast_reply.get("follow_up"), sum_of_first_text, last
                    )
                )
            else:
                prompt_to_show = fast_reply.get("clear_prompt")
                aisearch_payload = prompt_to_show
                if not aisearch:
                    temp_tasks = [
                        asyncio.create_task(
                            claude(single_entity_message, checking=False)
                        ),
                        asyncio.create_task(
                            calling_aisearch_without_saving(
                                aisearch_payload,
                                convId,
                                promptId,
                                es_client,
                                qdrant_client,
                                demoBlocked,
                                add_to_clear_prompt,
                            )
                        ),
                    ]

            if item.get("ambiguity"):
                rewritten_question = await ambiguous_task
                if rewritten_question:
                    break_flag = True
                    async for chunk in stream_openai_text(rewritten_question):
                        return_payload = {
                            "step": "text_line",
                            "text": chunk,
                            "response_id": count_response,
                        }
                        yield last_converter(return_payload)
                        sum_of_first_text += chunk

                    count_response += 1
                    questions_to_ask.append("Ambiguity")

        elif isinstance(item, dict) and "question" in item:
            question_agent_flag = True
            if item.get("question"):
                question_industry = item.get("industry_question", "")
                question_pureplay = item.get("pureplay_question", "")

                if question_industry:
                    question_agent_flag = False
                elif not question_industry and industry_recruitment_question_task:
                    rewritten_question = await industry_recruitment_question_task
                    if rewritten_question:
                        break_flag = True
                        async for chunk in stream_openai_text(rewritten_question):
                            return_payload = {
                                "step": "text_line",
                                "text": chunk,
                                "response_id": count_response,
                            }
                            yield last_converter(return_payload)
                            sum_of_first_text += chunk
                        count_response += 1
                        questions_to_ask.append("Industry")

                question_industry_task = []
                if question_pureplay and isinstance(question_pureplay, str):
                    last = True if count == 3 and break_flag else False
                    rewritten_question = await writing_the_f_thing(
                        question_pureplay, sum_of_first_text, last
                    )
                    if rewritten_question:
                        if question_industry:
                            question_industry_task = asyncio.create_task(
                                writing_the_f_thing(
                                    question_industry,
                                    sum_of_first_text + f"{rewritten_question}",
                                    last,
                                )
                            )

                        break_flag = True
                        async for chunk in stream_openai_text(rewritten_question):
                            return_payload = {
                                "step": "text_line",
                                "text": chunk,
                                "response_id": count_response,
                            }
                            yield last_converter(return_payload)
                            sum_of_first_text += chunk
                        count_response += 1
                        questions_to_ask.append("Pure Play")

                if question_industry and isinstance(question_industry, str):
                    if question_industry_task:
                        rewritten_question = await question_industry_task
                    else:
                        rewritten_question = await writing_the_f_thing(
                            question_industry, sum_of_first_text, last
                        )
                    if rewritten_question:
                        break_flag = True
                        async for chunk in stream_openai_text(rewritten_question):
                            return_payload = {
                                "step": "text_line",
                                "text": chunk,
                                "response_id": count_response,
                            }
                            yield last_converter(return_payload)
                            sum_of_first_text += chunk
                        count_response += 1
                        questions_to_ask.append("Industry")

        elif (
            isinstance(item, dict)
            and "recruitment_question" in item
            and item.get("recruitment_question")
        ):
            recruitment_questions_return_to_ask = list(item.keys())
            recruitment_questions_return_to_ask.remove("recruitment_question")
            awaited_question_task = None

            for index_number, key in enumerate(recruitment_questions_return_to_ask):
                if key == "recruitment_question":
                    continue
                if key == "industry" and not question_agent_flag:
                    industry_recruitment_question_task = asyncio.create_task(
                        writing_the_f_thing(item.get(key, ""), sum_of_first_text, last)
                    )
                    continue

                if not awaited_question_task:
                    rewritten_question = await writing_the_f_thing(
                        item.get(key), sum_of_first_text, False
                    )
                else:
                    rewritten_question = await awaited_question_task
                    awaited_question_task = None

                if rewritten_question:
                    if (
                        index_number + 1 < len(recruitment_questions_return_to_ask)
                    ) and (
                        recruitment_questions_return_to_ask[index_number + 1]
                        != "industry"
                        or question_agent_flag
                    ):
                        awaited_question_task = asyncio.create_task(
                            writing_the_f_thing(
                                item.get(
                                    recruitment_questions_return_to_ask[
                                        index_number + 1
                                    ]
                                ),
                                sum_of_first_text + f"{rewritten_question}",
                                last,
                            )
                        )

                    break_flag = True
                    async for chunk in stream_openai_text(rewritten_question):
                        return_payload = {
                            "step": "text_line",
                            "text": chunk,
                            "response_id": count_response,
                        }
                        yield last_converter(return_payload)
                        sum_of_first_text += chunk
                    count_response += 1
                    questions_to_ask.append(key)

        elif isinstance(item, str):
            pure_play_string = item
            if pure_play_string and isinstance(pure_play_string, str):
                last = True if count == 3 and break_flag else False
                rewritten_question = await writing_the_f_thing(
                    pure_play_string, sum_of_first_text, last
                )
                if rewritten_question:
                    break_flag = True
                    async for chunk in stream_openai_text(rewritten_question):
                        return_payload = {
                            "step": "text_line",
                            "text": chunk,
                            "response_id": count_response,
                        }
                        yield last_converter(return_payload)
                        sum_of_first_text += chunk
                    count_response += 1
                    questions_to_ask.append("Pure Play")

        count += 1

    if sum_of_first_text:
        sum_of_first_text
        asyncio.create_task(
            insert_into_cache_single_entity_results(
                convId,
                promptId,
                1,
                main_query,
                {"System Follow Up": sum_of_first_text, "questions": questions_to_ask},
            )
        )

    # if break_flag:
    #     return

    if fast_reply.get("clear_prompt", ""):
        return_payload = {
            "step": "rewritten_prompt",
            "text": fast_reply,
            "response_id": 1,
        }
        yield last_converter(return_payload)

    if not break_flag:
        async for chunk in handling_fast_reply(fast_reply, count_response):
            yield chunk

    count_response += 1
    clear_prompt_shown = False

    ambiguity = aisearch_results = None
    if not aisearch:
        response_entity, aisearch_results = await asyncio.gather(*temp_tasks)
    else:
        response_entity, ambiguity = await asyncio.gather(*temp_tasks)  # The rest

    results = []
    tasks = []
    index = 1
    if response_entity.get("single_entity", 0) and not break_flag:
        # async for chunk in handling_fast_reply(fast_reply, count_response):
        #     yield chunk
        # count_response += 1
        async for chunk in single_entity_processing(
            response_entity,
            tasks,
            convId,
            promptId,
            main_query,
            count_response,
            company_keys,
            person_keys,
            count_response,
            es_client,
        ):
            yield chunk
        return

    if not fast_reply.get("ambiguity", 0) and not aisearch and not break_flag:
        count_response = count_response + 1

        # async for chunk in handling_fast_reply(fast_reply, count_response):
        #     yield chunk
        # count_response += 1

        async for chunk in processing_aisearch_results(
            aisearch_results, count_response, aisearch_payload, convId, promptId
        ):
            yield chunk

        results.append(
            {
                "AI_Search_Results": aisearch_results,
                "clear_prompt": aisearch_payload,
            }
        )
    elif not fast_reply.get("ambiguity", 0) and aisearch:
        count_response = count_response + 1
        temp = ""
        async for chunk in processing_modification(
            count_response,
            ambiguity,
            demoBlocked,
            aisearch,
            convId,
            promptId,
            main_query,
            fast_reply,
        ):
            if chunk != "None" and not break_flag:
                yield chunk
                temp += chunk

        if chunk and chunk != "None" and not break_flag:
            asyncio.create_task(
                suggestions_preparations(
                    main_query,
                    convId,
                    promptId,
                    es_client,
                    already_suggested_list,
                    demoBlocked=demoBlocked,
                    context=full_context,
                )
            )
            return
        if chunk == "None":
            if ambiguity and ambiguity.get("clear_prompt", ""):
                aisearch_payload = ambiguity.get("clear_prompt", "")
            else:
                aisearch_payload = prompt_to_show
            asyncio.create_task(
                suggestions_preparations(
                    aisearch_payload,
                    convId,
                    promptId,
                    es_client,
                    already_suggested_list,
                    demoBlocked=demoBlocked,
                )
            )
            subtasks = asyncio.create_task(
                aisearch_new(
                    main_query,
                    es_client,
                    qdrant_client,
                    demoBlocked=demoBlocked,
                    add_to_clear_prompt=add_to_clear_prompt,
                )
            )
            timeline_ambiguity_task = asyncio.create_task(
                and_timeline_ambiguity_detection_agent(full_context)
            )
            company_timeline_ambiguity = await timeline_ambiguity_task
            # if (
            #     "ambiguity" in company_timeline_ambiguity
            #     and not company_timeline_ambiguity.get("ambiguity", 0)
            # ):
            #     if not break_flag:
            #         clear_prompt_shown = True
            #         async for chunk in handling_fast_reply(fast_reply, count_response):
            #             yield chunk
            #         count_response += 1
            #     else:
            #         return

            temp_filters = await subtasks

            if (
                "companies" in temp_filters
                and "ambiguity" in company_timeline_ambiguity
            ):
                company_dict = temp_filters.get("companies", {})
                if "and" in company_dict.get(
                    "timeline", ""
                ).lower() and company_timeline_ambiguity.get("ambiguity", 0):
                    and_question = f"""o you want only those people who are currently in the **{company_dict.get("current", [])[0]}** and previously used to be in **{company_dict.get("past", [])[0]}**?"""
                    if break_flag:
                        and_question = "- Lastly, d" + and_question
                    else:
                        and_question = "- D" + and_question
                    rewritten_question = await asyncio.create_task(
                        writing_the_f_thing(and_question, sum_of_first_text, True)
                    )
                    if rewritten_question:
                        break_flag = True
                        async for chunk in stream_openai_text(rewritten_question):
                            return_payload = {
                                "step": "text_line",
                                "text": chunk,
                                "response_id": count_response,
                            }
                            yield last_converter(return_payload)
                            sum_of_first_text += chunk
                    asyncio.create_task(
                        insert_into_cache_single_entity_results(
                            convId,
                            promptId,
                            count_response,
                            main_query,
                            {"System Follow Up": and_question, "and_question": True},
                        )
                    )
                    asyncio.create_task(
                        insert_into_cache_single_entity_results(
                            convId,
                            promptId,
                            -122,
                            main_query,
                            {"selected_filters": temp_filters},
                            temp=True,
                        )
                    )
                    return
            if not break_flag:
                # if fast_reply and not clear_prompt_shown:
                #     async for chunk in handling_fast_reply(fast_reply, count_response):
                #         yield chunk
                #     count_response += 1
                async for chunk in new_aisearch_results(
                    aisearch_payload,
                    temp_filters,
                    count_response,
                    convId,
                    promptId,
                    main_query,
                ):
                    yield chunk

    if tasks:
        await asyncio.gather(*tasks)
    elif results:
        asyncio.create_task(
            insert_into_cache_single_entity_results(
                convId, promptId, count_response, main_query, results[0]
            )
        )

    return


async def person_mapped_results(
    convId,
    promptId,
    response_id,
    es_client,
    primary_identifier=None,
    reason="update_identifier",
    prompt="",
    profile_count=0,
    result_db=None,
    manual=True,
):
    if reason == "update_identifier":
        async for chunk in update_value_publicIdentifiers(
            convId, promptId, response_id, primary_identifier, es_client
        ):
            yield chunk

    elif reason == "filters":
        if result_db.get("specific_name_search"):
            result_db = {
                "User_Selected_Following_Profile": result_db.get("specific_name_search")
            }
        else:
            result_db = {"AI_Search_Results": result_db}
        success = await filters_modification_in_db(
            convId, promptId, response_id, prompt, result_db
        )
        yield last_converter({"result": success})
    elif reason == "suggestions":
        async for chunk in suggestions(
            convId, promptId, response_id, prompt, False, result_db, manual, es_client
        ):
            yield chunk
    elif reason == "profile_count":
        success = await profile_count_modification_in_db(
            convId, promptId, response_id, prompt, profile_count
        )
        yield last_converter({"result": success})
    elif reason == "variants":
        async for chunk in call_for_variants(
            convId, promptId, response_id, es_client, result_db
        ):
            yield chunk

    elif reason == "expansion":
        async for chunk in call_for_expansion(
            convId, promptId, response_id, es_client, result_db, prompt
        ):
            yield chunk
    return
