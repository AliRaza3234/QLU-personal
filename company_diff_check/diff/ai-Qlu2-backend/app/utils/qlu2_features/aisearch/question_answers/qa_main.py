import asyncio

from app.utils.qlu2_features.aisearch.utilities.general.fast_utils import (
    writing_the_f_thing,
    streaming_the_f_thing,
)

from app.utils.qlu2_features.aisearch.question_answers.qa_agents import (
    generate_reply_agent,
    pre_questions_coro,
    new_industry_question_agent,
    new_pureplay_question_agent,
    get_recruitment_query_questions,
    executive_query_detection_agent,
)

from app.utils.qlu2_features.aisearch.utilities.helper_functions.misc_functions import (
    last_converter,
)

from app.utils.qlu2_features.aisearch.constants.shared_state import ASYNC_TASKS
from app.utils.qlu2_features.aisearch.utilities.helper_functions.streaming_functions import (
    stream_openai_text,
)

from app.utils.qlu2_features.aisearch.constants.aisearch_constants import PREFIX_STATE
from app.utils.qlu2_features.aisearch.utilities.helper_functions.postgres_functions import (
    insert_into_cache_single_entity_results,
)

from app.utils.qlu2_features.aisearch.question_answers.qa_utils import (
    get_industry_breakdown_question_task_from_ner,
    back_up_industry_detection_and_question_agent,
)


async def questions_full_flow(
    convId,
    promptId,
    main_query,
    string_second_string,
    last_suggestion,
    questions,
    demoBlocked,
    full_context,
    clarification,
    break_flag_event,
    suggestions_acceptance_event,
    shady_key,
    identified_industries_str,
):

    fast_task = asyncio.create_task(
        generate_reply_agent(
            convId=convId,
            promptId=promptId,
            main_query=main_query,
            string_second_string=string_second_string,
            last_suggestion=last_suggestion,
            questions=questions,
            demoBlocked=demoBlocked,
        )
    )

    if not shady_key:

        back_up_industry_breakdown_question_task = asyncio.create_task(
            back_up_industry_detection_and_question_agent(
                convId, promptId, main_query, demoBlocked
            )
        )

        ner_industry_breakdown_question_task = asyncio.create_task(
            get_industry_breakdown_question_task_from_ner(convId, promptId)
        )

        get_recruitment_task = asyncio.create_task(
            get_recruitment_query_questions(full_context, clarification)
        )

        is_executive_query = await executive_query_detection_agent(full_context)

        questions_tasks_list = [
            fast_task,
            get_recruitment_task,
            ner_industry_breakdown_question_task,
            back_up_industry_breakdown_question_task,
        ]

    else:
        is_executive_query = False
        questions_tasks_list = [fast_task]

    count_response = ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"].get(
        "count_response", 1
    )
    break_flag = False
    questions_to_ask = []
    sum_of_first_text = ""
    industry_question_asked = ""
    clear_prompt = ""
    fast_reply = {}
    all_targets = ""
    general_industry_question = ""
    industry_breakdown_question = ""

    for coro in asyncio.as_completed(questions_tasks_list):
        item = await coro
        if isinstance(item, dict) and "ambiguity" in item:
            fast_reply = item

            if item.get("ambiguity"):
                count_response += 1
                async for chunk in streaming_the_f_thing(
                    fast_reply.get("follow_up"), sum_of_first_text
                ):
                    return_payload = {
                        "step": "text_line",
                        "text": chunk,
                        "response_id": count_response,
                    }
                    yield last_converter(return_payload)
                    sum_of_first_text += chunk
                break_flag = True
                questions_to_ask.append("Ambiguity")
            else:
                clear_prompt = fast_reply.get("clear_prompt")

            # Breaking from the loop if query is non executive since we don't need to ask questions, other than general ambiguity
            if not is_executive_query:
                break

        elif (
            isinstance(item, dict)
            and ("industry_question" in item)
            and not industry_question_asked
            and is_executive_query
        ):
            industry_question = item.get("industry_question", "")
            if industry_question:
                count_response += 1
                async for chunk in streaming_the_f_thing(
                    industry_question, sum_of_first_text
                ):
                    return_payload = {
                        "step": "text_line",
                        "text": chunk,
                        "response_id": count_response,
                    }
                    yield last_converter(return_payload)
                    sum_of_first_text += chunk

                break_flag = True
                industry_question_asked = True
                questions_to_ask.append("Industry")
                all_targets = item.get("identified_industries_list", "")
                industry_breakdown_question = industry_question

            source = item.get("source", "")
            if source == "ner":
                try:
                    back_up_industry_breakdown_question_task.cancel()
                except asyncio.CancelledError as e:
                    print(e)
            elif source == "converse":
                try:
                    ner_industry_breakdown_question_task.cancel()
                except asyncio.CancelledError as e:
                    print(e)

        elif (
            isinstance(item, dict)
            and ("recruitment_question" in item)
            and is_executive_query
        ):
            possible_recruitment_questions_keys = [
                # "industry",
                "client_company",
                "skills",
                "title_variation",
                "acronym",
            ]

            question_keys = []
            for key, value in item.items():
                if key != "recruitment_question":
                    question_keys.append(key)

            if len(question_keys) == 1 and "skills" in question_keys:
                continue

            for key, value in item.items():
                if key == "industry":
                    general_industry_question = value
                    continue
                if key in possible_recruitment_questions_keys:
                    count_response += 1
                    async for chunk in streaming_the_f_thing(value, sum_of_first_text):
                        return_payload = {
                            "step": "text_line",
                            "text": chunk,
                            "response_id": count_response,
                        }
                        yield last_converter(return_payload)
                        sum_of_first_text += chunk

                    break_flag = True
                    questions_to_ask.append(key)

    # If no target is identified, and user has asked about Industry Breakdown, then ask about general industry
    if not industry_question_asked and general_industry_question:
        count_response += 1
        async for chunk in streaming_the_f_thing(
            general_industry_question, sum_of_first_text
        ):
            return_payload = {
                "step": "text_line",
                "text": chunk,
                "response_id": count_response,
            }
            yield last_converter(return_payload)
            sum_of_first_text += chunk
        break_flag = True
        questions_to_ask.append("industry")

    ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"]["fast_reply"] = fast_reply

    await suggestions_acceptance_event.wait()
    suggestions_acceptance = ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"].get(
        "suggestions_acceptance", ""
    )

    if not break_flag and not suggestions_acceptance:
        ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"]["count_response"] = (
            count_response + 2
        )
        ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"][
            "sum_of_first_text"
        ] = sum_of_first_text
        ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"]["break_flag"] = False
        ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"][
            "clear_prompt"
        ] = clear_prompt
        break_flag_event.set()
        async for chunk in stream_openai_text(clear_prompt):
            return_payload = {
                "step": "text_line",
                "text": chunk,
                "response_id": count_response,
            }
            yield last_converter(return_payload)
        stream_clear_prompt = False
        count_response += 1

        # return rewritten query
        return_payload = {
            "step": "rewritten_query",
            "text": clear_prompt,
            "response_id": count_response,
        }
        yield last_converter(return_payload)
    else:
        ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"]["break_flag"] = True
        ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"][
            "sum_of_first_text"
        ] = sum_of_first_text
        ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"]["count_response"] = (
            count_response + 1
        )
        break_flag_event.set()

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

    all_targets = str(identified_industries_str) + str(all_targets)

    if industry_breakdown_question:
        all_targets = f"{industry_breakdown_question}\n" + str(all_targets)

    asyncio.create_task(
        insert_into_cache_single_entity_results(
            convId,
            promptId,
            -1216,  # one after magna carta
            main_query,
            {"identified_industries_list": all_targets},
            temp=True,
        )
    )

    # deleting the stream object upon exiting the questions flow
    if f"{convId}_{promptId}_industry_stream" in ASYNC_TASKS:
        del ASYNC_TASKS[f"{convId}_{promptId}_industry_stream"]
    if f"{convId}_{promptId}_industry_question_task" in ASYNC_TASKS:
        del ASYNC_TASKS[f"{convId}_{promptId}_industry_question_task"]
