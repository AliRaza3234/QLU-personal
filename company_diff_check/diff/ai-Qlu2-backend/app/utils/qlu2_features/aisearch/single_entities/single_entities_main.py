import asyncio
import time

from app.utils.qlu2_features.aisearch.constants.aisearch_constants import (
    PERSON_KEYS,
    COMPANY_KEYS,
)

from app.utils.qlu2_features.aisearch.single_entities.single_entities_prompts import (
    SINGLE_ENTITY_DETECTION,
    SINGLE_ENTITY_CLASSIFIER_AGENT,
    SINGLE_ENTITY_PLANNER_AGENT,
)

from app.utils.qlu2_features.aisearch.utilities.llm_functions.llms import (
    claude,
    call_gpt_4_1_with_processing,
)
from app.utils.qlu2_features.aisearch.utilities.helper_functions.postgres_functions import (
    fetch_from_cache_single_entity_results,
)
from app.utils.qlu2_features.aisearch.single_entities.single_entities_utils import (
    single_entity_processing,
)

from app.utils.qlu2_features.aisearch.constants.shared_state import ASYNC_TASKS
from app.utils.qlu2_features.aisearch.constants.aisearch_constants import PREFIX_STATE


async def single_entity_classification_planning(user_prompt):

    classifier_task = [
        {"role": "system", "content": SINGLE_ENTITY_CLASSIFIER_AGENT},
        {"role": "user", "content": user_prompt},
    ]
    planner_task = [
        {"role": "system", "content": SINGLE_ENTITY_PLANNER_AGENT},
        {"role": "user", "content": user_prompt},
    ]

    classifier_result = asyncio.create_task(
        call_gpt_4_1_with_processing(classifier_task)
    )

    planner_result = asyncio.create_task(call_gpt_4_1_with_processing(planner_task))

    classification = await classifier_result
    json_to_return = {}
    if not classification.get("single_entity", 0):
        return {"single_entity": 0}
    else:
        json_to_return["single_entity"] = 1

    plan = await planner_result
    json_to_return["plan"] = plan.get("plan", [])

    return json_to_return


async def single_entity_full_flow(
    convId,
    promptId,
    main_query,
    visible_profiles,
    string_second_string,
    es_client,
    break_flag_event,
    single_entity_flag_event,
    suggestions_acceptance_event,
    add_to_clear_prompt_event,
):

    user_prompt_single = f"""<User_Prompt>{main_query}</User_Prompt>"""

    if string_second_string:
        user_prompt_single = f"""<Whole_Conversation>\n{string_second_string}<Last_Query>\n{main_query}\n</Last_Query>\n<Whole_Conversation>\n Consider ALL the previous queries and their results as well. Consider that system follow ups were asked to the user by your brother agent; if the user is clarifying something from before then you must take the WHOLE relevant conversation into account. Take a deep breath and reason logically about how and whether the new prompt relates to the previous ones (can also use identifiers if you know of them)."""

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

    # response_entity_task = asyncio.create_task(
    #     claude(single_entity_message, checking=False)
    # )

    user_prompt_single = user_prompt_single + (
        f"""<Profiles_User_Is_Seeing>\n{visible_profiles}\n</Profiles_User_Is_Seeing>"""
        if visible_profiles
        else ""
    )
    response_entity_task = asyncio.create_task(
        single_entity_classification_planning(user_prompt_single)
    )

    # If any question is asked returning to the main flow, since there's no need to continue with single entity detection
    await break_flag_event.wait()
    if ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"]["break_flag"]:
        single_entity_flag_event.set()
        return

    # If any suggestion was accepted, returning to the main flow, since there's no need to continue with single entity detection
    await suggestions_acceptance_event.wait()
    suggestions_acceptance = ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"].get(
        "suggestions_acceptance", ""
    )
    if suggestions_acceptance:
        single_entity_flag_event.set()
        return

    # If AND question was accepted, returning to the main flow, since there's no need to continue with single entity detection
    await add_to_clear_prompt_event.wait()
    if ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"].get(
        "and_question_acceptance", ""
    ):
        single_entity_flag_event.set()
        return

    count_response = ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"].get(
        "count_response", 2
    )

    response_entity = await response_entity_task

    tasks = []
    index = 1
    results = []

    if response_entity.get("single_entity", 0):
        ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"]["single_entity_flag"] = True
        single_entity_flag_event.set()
        async for chunk in single_entity_processing(
            response_entity=response_entity,
            tasks=tasks,
            convId=convId,
            promptId=promptId,
            main_query=main_query,
            index=count_response,
            company_keys=COMPANY_KEYS,
            person_keys=PERSON_KEYS,
            count_response=count_response,
            es_client=es_client,
        ):
            yield chunk
        return
    else:
        ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"]["single_entity_flag"] = False
        single_entity_flag_event.set()
        return
