from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import json
from app.utils.outreach.services.chat_services.converse import converse
from app.models.schemas.outreach.converse import ConverseRequest
from app.routes.dependancies import get_es_client
from fastapi import APIRouter, Depends
from elasticsearch import AsyncElasticsearch

from fastapi import APIRouter

router = APIRouter()


@router.post("/chat")
async def chat(
    request: ConverseRequest, es_client: AsyncElasticsearch = Depends(get_es_client)
):
    message = request.message
    conv_id = request.conv_id
    sender_name = request.sender_name
    campaign_profiles = request.campaign_profiles
    rounds = request.rounds
    round_messages = request.round_messages
    context_summary = request.context_summary
    agent_type = request.agent_type
    selected_profile = request.selected_profile

    async def event_stream():
        async for event in converse(
            message=message,
            conv_id=conv_id,
            sender_name=sender_name,
            campaign_profiles=campaign_profiles,
            es_client=es_client,
            rounds=rounds,
            round_messages=round_messages,
            context_summary=context_summary,
            agent_type=agent_type,
            selected_profile=selected_profile,
        ):
            yield json.dumps(event) + "\n"

    return StreamingResponse(event_stream(), media_type="application/json")
