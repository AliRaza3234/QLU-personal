import asyncio
from app.utils.aisearch_final.complete_aisearch import test_main as aisearch_new

from app.utils.qlu2_features.aisearch.utilities.helper_functions.postgres_functions import (
    insert_into_cache_single_entity_results,
)
from app.utils.qlu2_features.aisearch.utilities.helper_functions.misc_functions import (
    last_converter,
)

from app.utils.qlu2_features.aisearch.filters.filters_utils import (
    processing_aisearch_results,
    new_aisearch_results,
)
from app.utils.qlu2_features.aisearch.suggestions.suggestions_utils import (
    suggestions_preparations,
)

from app.utils.qlu2_features.aisearch.constants.shared_state import ASYNC_TASKS
from app.utils.qlu2_features.aisearch.utilities.helper_functions.streaming_functions import (
    stream_openai_text,
)

from app.utils.qlu2_features.aisearch.utilities.general.fast_utils import (
    writing_the_f_thing,
)
from app.utils.qlu2_features.aisearch.constants.aisearch_constants import PREFIX_STATE


async def aisearch_filters_flow(
    convId,
    promptId,
    main_query,
    aisearch,
    last_aisearch,
    demoBlocked,
    already_suggested_list,
    es_client,
    qdrant_client,
    break_flag_event,
    single_entity_flag_event,
    add_to_clear_prompt_event,
    timeline_ambiguity_task,
    suggestions_acceptance_event,
):

    results = []
    add_to_clear_prompt = ""

    if promptId == 1 or last_aisearch:

        if not last_aisearch:
            asyncio.create_task(
                suggestions_preparations(
                    query=main_query,
                    convId=convId,
                    promptId=promptId,
                    es_client=es_client,
                    already_given_suggestions=already_suggested_list,
                    demoBlocked=demoBlocked,
                )
            )

            aisearch_task = asyncio.create_task(
                aisearch_new(
                    main_query,
                    es_client,
                    qdrant_client,
                    demoBlocked=demoBlocked,
                    convId=convId,
                    promptId=promptId,
                )
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
            # Get values of these from async_tasks
            count_response = (
                ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"]["count_response"] + 1
            )
            sum_of_first_text = ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"].get(
                "sum_of_first_text", ""
            )
            break_flag = ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"].get(
                "break_flag", ""
            )

            company_timeline_ambiguity = await timeline_ambiguity_task

            temp_filters = await aisearch_task

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
    else:

        await break_flag_event.wait()
        break_flag = ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"].get(
            "break_flag", ""
        )
        if break_flag:
            return

        await suggestions_acceptance_event.wait()
        suggestions_acceptance = ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"].get(
            "suggestions_acceptance", ""
        )
        if suggestions_acceptance:
            return

        await single_entity_flag_event.wait()
        single_entity_flag = ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"].get(
            "single_entity_flag", ""
        )
        if single_entity_flag:
            return

        await add_to_clear_prompt_event.wait()
        if ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"].get(
            "and_question_acceptance", ""
        ):
            return

        add_to_clear_prompt = ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"].get(
            "add_to_clear_prompt", ""
        )

        count_response = ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"].get(
            "count_response", 2
        )
        if not aisearch and not break_flag:

            aisearch_payload = ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"][
                "clear_prompt"
            ]

            asyncio.create_task(
                suggestions_preparations(
                    aisearch_payload,
                    convId,
                    promptId,
                    es_client,
                    demoBlocked=demoBlocked,
                )
            )

            aisearch_task = asyncio.create_task(
                aisearch_new(
                    aisearch_payload,
                    es_client,
                    qdrant_client,
                    demoBlocked=demoBlocked,
                    add_to_clear_prompt=add_to_clear_prompt,
                    convId=convId,
                    promptId=promptId,
                )
            )
            aisearch_results = await aisearch_task

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

            asyncio.create_task(
                insert_into_cache_single_entity_results(
                    convId, promptId, count_response, main_query, results[0]
                )
            )
