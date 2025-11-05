from fastapi import APIRouter, HTTPException, Depends
import traceback
from app.routes.dependancies import get_es_client
from qutils.slack.notifications import send_slack_notification
from fastapi.responses import JSONResponse
from app.models.schemas.outreach.miniature_round import (
    MiniatureRoundIn,
    MiniatureRoundOut,
)
from app.utils.outreach.services.dynamic_services.dynamic import get_miniature_round

router = APIRouter()


@router.post("/get_miniature_round", response_model=MiniatureRoundOut)
async def miniature_round(req: MiniatureRoundIn, es_client=Depends(get_es_client)):
    try:
        if req.channel not in ["email", "text"]:
            raise HTTPException(status_code=400, detail="Invalid channel")
        res = await get_miniature_round(
            req.call_pitch, req.channel, req.es_id, es_client
        )
        return JSONResponse(status_code=200, content=res)
    except Exception as e:
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=req,
            route="get_miniature_round",
            service_name="OUTREACH",
        )
        raise HTTPException(status_code=500, detail=str(e))
