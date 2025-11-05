from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.models.schemas.outreach.ai_template import (
    AIGenCampaignResponse,
    AIGenCampaignRequest,
)
from app.utils.outreach.services.ai_template_services.ai_template import (
    ai_generated_campaign,
)
from app.routes.dependancies import get_es_client
from fastapi import APIRouter, HTTPException, Depends
from elasticsearch import AsyncElasticsearch
import traceback

router = APIRouter()


@router.post("/ai_template", response_model=AIGenCampaignResponse)
async def ai_template(
    request: AIGenCampaignRequest,
    es_client: AsyncElasticsearch = Depends(get_es_client),
):
    try:
        plan_dct = await ai_generated_campaign(
            assignment_name=request.assignment_name,
            total_profiles=request.total_profiles,
            sample_profiles=request.sample_profiles,
            channel_credits=request.channel_credits,
            creation_day=request.creation_day,
            es_client=es_client,
            sender_data=request.sender_data,
            override_sample=request.override_sample,
            profile_data=request.profile_data,
        )
        return JSONResponse(status_code=200, content=plan_dct)
    except Exception as e:
        error_trace = traceback.format_exc()
        raise HTTPException(
            status_code=500, detail={"error": str(e), "traceback": error_trace}
        )
