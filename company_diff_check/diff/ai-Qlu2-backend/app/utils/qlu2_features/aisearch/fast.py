import asyncio
import json

from app.utils.qlu2_features.aisearch.utilities.helper_functions.postgres_functions import (
    fetch_from_cache_single_entity_results,
    fetch_identified_industries_list,
)


from app.utils.qlu2_features.aisearch.question_answers.qa_main import (
    questions_full_flow,
)
from app.utils.qlu2_features.aisearch.single_entities.single_entities_main import (
    single_entity_full_flow,
)
from app.utils.qlu2_features.aisearch.filters.filters_main import aisearch_filters_flow
from app.utils.qlu2_features.aisearch.modifications.modifications_main import (
    modifications_full_flow,
)
from app.utils.qlu2_features.aisearch.suggestions.suggestions_acceptance import (
    handle_suggestions_acceptance,
)

from app.utils.qlu2_features.aisearch.utilities.general.fast_utils import (
    writing_the_f_thing,
    get_full_context,
    _as_task,
    company_timeline_confirmation,
)
from app.utils.qlu2_features.aisearch.constants.shared_state import ASYNC_TASKS
from app.utils.qlu2_features.aisearch.constants.aisearch_constants import PREFIX_STATE

from app.utils.qlu2_features.aisearch.question_answers.qa_agents import (
    timeline_selection_analysis_agent,
    and_timeline_ambiguity_detection_agent,
)


async def handle_chunks_stream(task, iterator):
    while True:
        try:
            chunk = await task
            if chunk is None:
                break
            else:
                yield chunk
                # Create the next task for the next iteration
                task = _as_task(iterator)
        except StopAsyncIteration:
            break
        except Exception as e:
            print(f"Error in chunks streaming: {e}")
            break


async def main(
    convId,
    promptId,
    main_query,
    visible_profiles,
    es_client,
    qdrant_client,
    demoBlocked=False,
    shady_key=False,
):

    string_second_string = ""
    aisearch = None
    industry_flag = False
    last_aisearch = None
    last_suggestion = {}
    identified_industries_str = ""
    already_suggested_list = []
    clarification = False
    questions = []
    company_question = False
    count_response = 1

    # Initiate the shared state for the conversation
    ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"] = {
        "count_response": count_response
    }

    if promptId > 1:
        identified_industries_str_task = asyncio.create_task(
            fetch_identified_industries_list(convId, promptId)
        )
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
        identified_industries_str = await identified_industries_str_task
        if not identified_industries_str:
            identified_industries_str = ""

    full_context = await get_full_context(string_second_string, main_query)

    # FLAGS AND EVENTS:
    break_flag_event = asyncio.Event()
    single_entity_flag_event = asyncio.Event()
    add_to_clear_prompt_event = asyncio.Event()
    suggestions_acceptance_event = asyncio.Event()

    timeline_ambiguity_task = asyncio.create_task(
        and_timeline_ambiguity_detection_agent(full_context)
    )

    # ITERATORS AND TASKS

    # ------------------------------------------------------------------------------------------------
    # Starting Single Entity Tasks
    # ------------------------------------------------------------------------------------------------

    single_entity_iterator = single_entity_full_flow(
        convId=convId,
        promptId=promptId,
        main_query=main_query,
        visible_profiles=visible_profiles,
        string_second_string=string_second_string,
        es_client=es_client,
        break_flag_event=break_flag_event,
        single_entity_flag_event=single_entity_flag_event,
        suggestions_acceptance_event=suggestions_acceptance_event,
        add_to_clear_prompt_event=add_to_clear_prompt_event,
    )
    single_entity_task = _as_task(single_entity_iterator)

    # ------------------------------------------------------------------------------------------------
    # Starting AI SEARCH Filters Tasks
    # ------------------------------------------------------------------------------------------------

    aisearch_filters_iterator = aisearch_filters_flow(
        convId=convId,
        promptId=promptId,
        main_query=main_query,
        aisearch=aisearch,
        last_aisearch=last_aisearch,
        demoBlocked=demoBlocked,
        already_suggested_list=already_suggested_list,
        es_client=es_client,
        qdrant_client=qdrant_client,
        break_flag_event=break_flag_event,
        single_entity_flag_event=single_entity_flag_event,
        timeline_ambiguity_task=timeline_ambiguity_task,
        add_to_clear_prompt_event=add_to_clear_prompt_event,
        suggestions_acceptance_event=suggestions_acceptance_event,
    )
    aisearch_filters_task = _as_task(aisearch_filters_iterator)

    # ------------------------------------------------------------------------------------------------
    # Starting Modification Tasks
    # ------------------------------------------------------------------------------------------------
    modifications_iterator = modifications_full_flow(
        convId=convId,
        promptId=promptId,
        main_query=main_query,
        string_second_string=string_second_string,
        last_suggestion=last_suggestion,
        industry_flag=industry_flag,
        aisearch=aisearch,
        last_aisearch=last_aisearch,
        demoBlocked=demoBlocked,
        full_context=full_context,
        already_suggested_list=already_suggested_list,
        es_client=es_client,
        qdrant_client=qdrant_client,
        break_flag_event=break_flag_event,
        single_entity_flag_event=single_entity_flag_event,
        add_to_clear_prompt_event=add_to_clear_prompt_event,
        timeline_ambiguity_task=timeline_ambiguity_task,
        suggestions_acceptance_event=suggestions_acceptance_event,
    )
    modifications_task = _as_task(modifications_iterator)

    # ------------------------------------------------------------------------------------------------
    # Starting Questions Tasks
    # ------------------------------------------------------------------------------------------------
    questions_iterator = questions_full_flow(
        convId=convId,
        promptId=promptId,
        main_query=main_query,
        string_second_string=string_second_string,
        last_suggestion=last_suggestion,
        questions=questions,
        demoBlocked=demoBlocked,
        full_context=full_context,
        clarification=clarification,
        break_flag_event=break_flag_event,
        suggestions_acceptance_event=suggestions_acceptance_event,
        shady_key=shady_key,
        identified_industries_str=identified_industries_str,
    )
    questions_task = _as_task(questions_iterator)

    # ------------------------------------------------------------------------------------------------
    # Suggestions Acceptance
    # ------------------------------------------------------------------------------------------------
    async for chunk in handle_suggestions_acceptance(
        convId=convId,
        promptId=promptId,
        main_query=main_query,
        last_suggestion=last_suggestion,
        already_suggested_list=already_suggested_list,
        full_context=full_context,
        count_response=ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"][
            "count_response"
        ],
        es_client=es_client,
        demoBlocked=demoBlocked,
    ):
        yield chunk
    suggestions_acceptance_event.set()

    # ------------------------------------------------------------------------------------------------
    # Company Timeline Confirmation - Getting the value of add_to_clear_prompt
    # ------------------------------------------------------------------------------------------------

    add_to_clear_prompt = ""
    if company_question and not last_aisearch:
        company_timeline_task = asyncio.create_task(
            timeline_selection_analysis_agent(full_context)
        )
        async for chunk_comp in company_timeline_confirmation(
            company_timeline_task, main_query, convId, promptId, count_response
        ):
            if chunk_comp and "add_to_clear_prompt" not in chunk_comp:
                yield chunk_comp

        if chunk_comp and "add_to_clear_prompt" not in chunk_comp:
            ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"][
                "and_question_acceptance"
            ] = True
            add_to_clear_prompt_event.set()
            return
        elif (
            chunk_comp
            and isinstance(chunk_comp, dict)
            and "add_to_clear_prompt" in chunk_comp
        ):
            add_to_clear_prompt = chunk_comp.get("add_to_clear_prompt", "")
        ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"][
            "add_to_clear_prompt"
        ] = add_to_clear_prompt

    add_to_clear_prompt_event.set()

    # Handling Questions Chunks
    async for questions_chunk in handle_chunks_stream(
        questions_task, questions_iterator
    ):
        yield questions_chunk

    # Handling Single Entity Chunks:
    async for single_entity_chunk in handle_chunks_stream(
        single_entity_task, single_entity_iterator
    ):
        yield single_entity_chunk

    # Handling AI Search Filters Chunks:
    async for aisearch_filters_chunk in handle_chunks_stream(
        aisearch_filters_task, aisearch_filters_iterator
    ):
        yield aisearch_filters_chunk

    # Handling Modifications Chunks:
    async for modifications_chunk in handle_chunks_stream(
        modifications_task, modifications_iterator
    ):
        yield modifications_chunk

    # Deleting the shared state
    del ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"]
    return
