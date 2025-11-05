import asyncio
from app.utils.aisearch_final.complete_aisearch import test_main as aisearch_new


from app.utils.qlu2_features.aisearch.utilities.llm_functions.llms import claude
from app.utils.qlu2_features.aisearch.utilities.helper_functions.postgres_functions import (
    insert_into_cache_single_entity_results,
)
from app.utils.qlu2_features.aisearch.utilities.helper_functions.misc_functions import (
    last_converter,
)
from app.utils.qlu2_features.aisearch.modifications.modifications_utils import (
    processing_modification,
)
from app.utils.qlu2_features.aisearch.filters.filters_utils import new_aisearch_results
from app.utils.qlu2_features.aisearch.suggestions.suggestions_utils import (
    suggestions_preparations,
)

from app.utils.qlu2_features.aisearch.constants.shared_state import ASYNC_TASKS
from app.utils.qlu2_features.aisearch.constants.aisearch_constants import PREFIX_STATE
from app.utils.qlu2_features.aisearch.utilities.helper_functions.streaming_functions import (
    stream_openai_text,
)
from app.utils.qlu2_features.aisearch.utilities.general.fast_utils import (
    writing_the_f_thing,
)

from app.utils.qlu2_features.aisearch.modifications.modifications_prompts import (
    DEMO_AMBIGUOUS_PROMPT_AISEARCH,
    DEMO_AMBIGUOUS_PROMPT_AISEARCH_INDUSTRY,
    NO_DEMO_AMBIGUOUS_PROMPT_AISEARCH,
    NO_DEMO_AMBIGUOUS_PROMPT_AISEARCH_INDUSTRY,
)


async def modifications_full_flow(
    convId,
    promptId,
    main_query,
    string_second_string,
    last_suggestion,
    industry_flag,
    aisearch,
    last_aisearch,
    demoBlocked,
    full_context,
    already_suggested_list,
    es_client,
    qdrant_client,
    break_flag_event,
    single_entity_flag_event,
    add_to_clear_prompt_event,
    timeline_ambiguity_task,
    suggestions_acceptance_event,
):

    if demoBlocked:
        AMBIGUOUS_PROMPT_AISEARCH = NO_DEMO_AMBIGUOUS_PROMPT_AISEARCH
        AMBIGUOUS_PROMPT_AISEARCH_INDUSTRY = NO_DEMO_AMBIGUOUS_PROMPT_AISEARCH_INDUSTRY
    else:
        AMBIGUOUS_PROMPT_AISEARCH = DEMO_AMBIGUOUS_PROMPT_AISEARCH
        AMBIGUOUS_PROMPT_AISEARCH_INDUSTRY = DEMO_AMBIGUOUS_PROMPT_AISEARCH_INDUSTRY

    modification_user_prompt = f"""<User_Prompt>\n{main_query}\n</User_Prompt>"""

    if string_second_string:
        modification_user_prompt = f"""<Whole_Conversation>\n{string_second_string}<Last_Query>\n{main_query}\n</Last_Query>\n<Whole_Conversation>\n Consider the previous queries and their results as well. Consider that system follow ups were asked to the user by your brother agent and take them into account as well, unless the user is introducing something completely new.
        """

    if last_suggestion:
        modification_user_prompt += """If the suggestions agent had asked something before and the user has replied to them, take it into account as well based on what the suggestion was."""

    if industry_flag:
        modification_user_prompt += """ If the user had been suggested adding industries which would fit as an exact industry keyword then only industry attribute would be required with instructions to add the exact mentioned keywords, but if the user doesn't mean an exact industry keyword then company should be called. As in if the suggestion was to add the related industries 'manufacturing', 'marketting' then the instruction should be to "Add the industry keywords: 'manufacturing' and 'marketting' as industries only" and ***industry** attribute should be called, **not** the company_product filter (In such cases, instruction should be to add only the keywords required by the user and not generate synonyms).
        """

    MODIFICATION_FOLLOW_UP_SYSTEM_PROMPT = (
        AMBIGUOUS_PROMPT_AISEARCH
        if not industry_flag
        else AMBIGUOUS_PROMPT_AISEARCH_INDUSTRY
    )

    modification_detector = [
        {"role": "system", "content": MODIFICATION_FOLLOW_UP_SYSTEM_PROMPT},
        {"role": "user", "content": modification_user_prompt},
    ]

    if promptId == 1 or last_aisearch:
        if last_aisearch:
            ambiguity = await claude(
                modification_detector,
                model="anthropic/claude-sonnet-4-20250514",
                checking=False,
            )

            await suggestions_acceptance_event.wait()
            suggestions_acceptance = ASYNC_TASKS[
                f"{PREFIX_STATE}_{convId}_{promptId}"
            ].get("suggestions_acceptance", "")
            if suggestions_acceptance:
                return

            await single_entity_flag_event.wait()
            single_entity_flag = ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"].get(
                "single_entity_flag", ""
            )
            if single_entity_flag:
                return

            await break_flag_event.wait()
            break_flag = ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"].get(
                "break_flag", ""
            )

            rewritten_query = ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"].get(
                "clear_prompt", ""
            )
            count_response = ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"][
                "count_response"
            ]
            sum_of_first_text = ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"].get(
                "sum_of_first_text", ""
            )
            break_flag = ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"].get(
                "break_flag", ""
            )

            temp = ""
            async for chunk in processing_modification(
                count_response=count_response,
                ambiguity=ambiguity,
                demoBlocked=demoBlocked,
                aisearch=aisearch,
                convId=convId,
                promptId=promptId,
                main_query=main_query,
            ):
                if chunk != "None" and not break_flag:
                    yield chunk
                    temp += chunk

            if chunk and chunk != "None" and not break_flag:
                asyncio.create_task(
                    suggestions_preparations(
                        query=main_query,
                        convId=convId,
                        promptId=promptId,
                        es_client=es_client,
                        already_given_suggestions=already_suggested_list,
                        demoBlocked=demoBlocked,
                        context=full_context,
                    )
                )
                return
            if chunk == "None":
                asyncio.create_task(
                    suggestions_preparations(
                        query=rewritten_query,
                        convId=convId,
                        promptId=promptId,
                        es_client=es_client,
                        already_given_suggestions=already_suggested_list,
                        demoBlocked=demoBlocked,
                        context=full_context,
                    )
                )
                subtasks = asyncio.create_task(
                    aisearch_new(
                        rewritten_query,
                        es_client,
                        qdrant_client,
                        demoBlocked=demoBlocked,
                        convId=convId,
                        promptId=promptId,
                    )
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
                        if rewritten_question and rewritten_question.get(
                            "industry_question"
                        ):
                            break_flag = True
                            async for chunk in stream_openai_text(
                                rewritten_question["industry_question"]
                            ):
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
                                {
                                    "System Follow Up": and_question,
                                    "and_question": True,
                                },
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
                        aisearch_payload=rewritten_query,
                        temp_filters=temp_filters,
                        count_response=count_response,
                        convId=convId,
                        promptId=promptId,
                        main_query=main_query,
                    ):
                        yield chunk
    else:

        if aisearch:
            ambiguity = await claude(
                modification_detector,
                model="anthropic/claude-sonnet-4-20250514",
                checking=False,
            )

            await suggestions_acceptance_event.wait()
            suggestions_acceptance = ASYNC_TASKS[
                f"{PREFIX_STATE}_{convId}_{promptId}"
            ].get("suggestions_acceptance", "")
            if suggestions_acceptance:
                return

            await add_to_clear_prompt_event.wait()
            if ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"].get(
                "and_question_acceptance", ""
            ):
                return

            await single_entity_flag_event.wait()
            single_entity_flag = ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"].get(
                "single_entity_flag", ""
            )
            if single_entity_flag:
                return

            await break_flag_event.wait()
            break_flag = ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"].get(
                "break_flag", ""
            )
            fast_reply = ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"].get(
                "fast_reply", {}
            )
            count_response = ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"].get(
                "count_response", 2
            )
            sum_of_first_text = ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"].get(
                "sum_of_first_text", ""
            )
            rewritten_query = ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"].get(
                "clear_prompt", ""
            )

            if not fast_reply.get("ambiguity", 0) and aisearch:

                count_response = count_response + 1
                temp = ""
                async for chunk in processing_modification(
                    count_response=count_response,
                    ambiguity=ambiguity,
                    demoBlocked=demoBlocked,
                    aisearch=aisearch,
                    convId=convId,
                    promptId=promptId,
                    main_query=main_query,
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
                    asyncio.create_task(
                        suggestions_preparations(
                            rewritten_query,
                            convId,
                            promptId,
                            es_client,
                            already_suggested_list,
                            demoBlocked=demoBlocked,
                        )
                    )

                    add_to_clear_prompt = ASYNC_TASKS[
                        f"{PREFIX_STATE}_{convId}_{promptId}"
                    ].get("add_to_clear_prompt", "")

                    subtasks = asyncio.create_task(
                        aisearch_new(
                            rewritten_query,
                            es_client,
                            qdrant_client,
                            demoBlocked=demoBlocked,
                            add_to_clear_prompt=add_to_clear_prompt,
                            convId=convId,
                            promptId=promptId,
                        )
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
                                writing_the_f_thing(
                                    and_question, sum_of_first_text, True
                                )
                            )
                            if rewritten_question and rewritten_question.get(
                                "industry_question"
                            ):
                                break_flag = True
                                async for chunk in stream_openai_text(
                                    rewritten_question["industry_question"]
                                ):
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
                                    {
                                        "System Follow Up": and_question,
                                        "and_question": True,
                                    },
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
                            rewritten_query,
                            temp_filters,
                            count_response,
                            convId,
                            promptId,
                            main_query,
                        ):
                            yield chunk

    return
