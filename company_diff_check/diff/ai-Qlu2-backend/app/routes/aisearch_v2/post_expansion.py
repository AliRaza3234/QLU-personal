import traceback
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.routes.dependancies import get_es_client
from app.models.schemas.aisearch import ExpansionAISearch
from app.utils.aisearch_expansion_variants.expansion import (
    expansion,
    industry_suggestions,
)
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/filters_expansion")
async def ai_search_expansion(
    input_payload: ExpansionAISearch, es_client=Depends(get_es_client)
):
    context = input_payload.context
    queries = input_payload.oldQueries

    try:
        response = await expansion(context, queries, es_client)
        return JSONResponse({"result": response})
    except Exception as e:
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=input_payload.dict(),
            route="/aisearch/filters_expansion",
            service_name="AISEARCH",
        )
        return JSONResponse(content={"message": "Error"}, status_code=500)


@router.post("/industry_suggestion")
async def ai_search_suggestions(
    input_payload: ExpansionAISearch, es_client=Depends(get_es_client)
):
    context = input_payload.context
    queries = input_payload.oldQueries

    try:
        response = await industry_suggestions(context, queries, es_client)
        return JSONResponse({"result": response})
    except Exception as e:
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=input_payload.dict(),
            route="/aisearch/industry_suggestion",
            service_name="AISEARCH",
        )
        return JSONResponse(content={"message": "Error"}, status_code=500)
