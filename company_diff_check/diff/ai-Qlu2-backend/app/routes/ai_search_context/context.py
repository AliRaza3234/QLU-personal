import traceback
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.models.schemas.ai_search_context.ai_search_context import *
from app.utils.ai_search_context.context_aisearch import (
    Evaluate_Extract_Modify,
    # context_main,
    context,
)
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/evaluation", response_model=ResponseEvaluationPayload)
async def context_evaluation(input_payload: EvaluationPayload):
    new_query = input_payload.newQuery
    old_queries = input_payload.oldQueries
    demoBlocked = input_payload.isDemographicsBlocked

    try:
        response = await Evaluate_Extract_Modify(new_query, old_queries, demoBlocked)
        output = ResponseEvaluationPayload(result=response)
        return output
    except Exception as e:
        print("Exception: ", e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=input_payload,
            route="evaluation",
            service_name="AISEARCH",
        )
        return JSONResponse(content={"message": "Error"}, status_code=500)


@router.post("/modification", response_model=ResponseModificationPayload)
async def context_modification(input_payload: ModificationPayload):
    newQuery = input_payload.newQuery
    results = input_payload.context
    entity = input_payload.entity

    try:
        response = await context(newQuery, results, entity)
        output = ResponseModificationPayload(result=response)
        return output
    except Exception as e:
        print("Exception: ", e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=input_payload,
            route="modification",
            service_name="AISEARCH",
        )
        return JSONResponse(content={"message": "Error"}, status_code=500)
