from app.utils.qlu2_features.aisearch.constants.shared_state import ASYNC_TASKS
import asyncio
from app.utils.qlu2_features.aisearch.question_answers.qa_agents import (
    create_industry_breakdown_question_task,
)


async def get_industry_breakdown_question_task_from_ner(convId, promptId):

    try:
        event_key = f"{convId}_{promptId}_industry_detection_event"
        event = ASYNC_TASKS.get(event_key, None)
        if event:
            await event.wait()

        industry_breakdown_question_task = ASYNC_TASKS.get(
            f"{convId}_{promptId}_industry_question_task", None
        )

        industry_breakdown_question_from_ner = None

        if isinstance(industry_breakdown_question_task, asyncio.Task):
            industry_breakdown_question_from_ner = (
                await industry_breakdown_question_task
            )

        if isinstance(industry_breakdown_question_from_ner, dict):
            industry_breakdown_question_from_ner["source"] = "ner"
            return industry_breakdown_question_from_ner
        else:
            return {}

    except Exception as e:
        print(e)
        return {}


async def back_up_industry_detection_and_question_agent(
    convId, promptId, new_text, demoBlocked=False
):

    industry_response = await create_industry_breakdown_question_task(
        convId, promptId, new_text, demoBlocked
    )

    if isinstance(industry_response, dict):
        industry_response["source"] = "converse"

    return industry_response
