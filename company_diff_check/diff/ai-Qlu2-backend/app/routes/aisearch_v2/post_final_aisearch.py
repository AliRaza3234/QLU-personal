import traceback
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.routes.dependancies import get_es_client, get_qdrant_client
from app.models.schemas.aisearch import FinalAISearch
from app.utils.aisearch_final.aisearch import main
from app.utils.aisearch_final.complete_aisearch import test_main, test_main_groq
from qutils.slack.notifications import send_slack_notification
import os

router = APIRouter()


@router.post("/extract_all_filters")
async def ai_search_all_filters(
    input_payload: FinalAISearch, es_client=Depends(get_es_client)
):
    text = input_payload.query
    demoBlocked = input_payload.isDemographicsBlocked

    try:
        response = await main(text, es_client, demoBlocked)
        return JSONResponse(response)
    except Exception as e:
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=input_payload.dict(),
            route="/aisearch/extract_all_filters",
            service_name="AISEARCH",
        )
        return JSONResponse(content={"message": "Error"}, status_code=500)


@router.post("/extract_all_filters_testing")
async def ai_search_all_filters1(
    input_payload: FinalAISearch,
    es_client=Depends(get_es_client),
    qdrant_client=Depends(get_qdrant_client),
):
    text = input_payload.query
    demoBlocked = input_payload.isDemographicsBlocked
    testing = input_payload.testing
    try:
        if not testing:  # and os.getenv("ENVIRONMENT", "") == "staging":
            response = await test_main_groq(text, es_client, qdrant_client, demoBlocked)
        else:
            response = await test_main(
                text, es_client, qdrant_client, demoBlocked, testing=testing
            )
        return JSONResponse(response)
    except Exception as e:
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=input_payload.dict(),
            route="/aisearch/extract_all_filters_testing",
            service_name="AISEARCH_TESTING",
        )
        return JSONResponse(content={"message": "Error"}, status_code=500)
