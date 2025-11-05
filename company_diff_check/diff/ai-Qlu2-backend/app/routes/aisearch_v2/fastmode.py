import traceback
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse

from app.routes.dependancies import get_es_client, get_qdrant_client
from app.models.schemas.aisearch import FastModeQuery, MappedPersonQuery
from app.utils.qlu2_features.aisearch.fast import main
from app.utils.qlu2_features.aisearch.utilities.general.fast_utils import (
    person_mapped_results,
)
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/single_entities")
async def ai_search_fast(
    input_payload: FastModeQuery,
    es_client=Depends(get_es_client),
    qdrant_client=Depends(get_qdrant_client),
):
    query = input_payload.query
    conversation_id = input_payload.conversation_id
    prompt_id = input_payload.prompt_id
    demoBlocked = input_payload.isDemographicsBlocked
    visible_profiles = input_payload.visible_profiles
    shady_key = input_payload.bakchodi

    try:
        return StreamingResponse(
            main(
                conversation_id,
                prompt_id,
                query,
                visible_profiles,
                es_client,
                qdrant_client,
                demoBlocked,
                shady_key,
            ),
            media_type="text/event-stream",
            headers={"Content-Type": "text/event-stream; charset=utf-8"},
        )
    except Exception as e:
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=input_payload.dict(),
            route="/aisearch_fastmode/fastmode",
            service_name="AI search fastmode",
        )
        return JSONResponse(content={"message": "Error"}, status_code=500)


@router.post("/updations")
async def ai_search_mapped_person(
    input_payload: MappedPersonQuery, es_client=Depends(get_es_client)
):
    identifier = input_payload.identifier
    conversation_id = input_payload.conversation_id
    prompt_id = input_payload.prompt_id
    response_id = input_payload.response_id
    reason = input_payload.reason
    prompt = input_payload.prompt
    filters = input_payload.filters
    profile_count = input_payload.profile_count
    if reason == "suggestions":
        manual = False
    elif reason == "manual_suggestions":
        manual = True
        reason = "suggestions"
    else:
        manual = True

    # manual = input_payload.manual

    try:
        return StreamingResponse(
            person_mapped_results(
                conversation_id,
                prompt_id,
                response_id,
                es_client,
                identifier,
                reason,
                prompt,
                profile_count,
                filters,
                manual,
            ),
            media_type="text/event-stream",
            headers={"Content-Type": "text/event-stream; charset=utf-8"},
        )
    except Exception as e:
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=input_payload.dict(),
            route="/aisearch_fastmode/fastmode",
            service_name="AISEARCH",
        )
        return JSONResponse(content={"message": "Error"}, status_code=500)
