from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.models.schemas.outreach.enhance_text import EnhanceRequest, EnhanceResponse
from app.utils.outreach.services.dynamic_services.dynamic import enhance_text
from qutils.slack.notifications import send_slack_notification
import traceback

router = APIRouter()


@router.post("/enhance_text", response_model=EnhanceResponse)
async def enhance(request: EnhanceRequest):
    text = request.text
    attributes = request.attributes
    sender_name = request.sender_name
    category = request.category
    channel = request.channel
    auto_enhance = request.auto_enhance
    try:
        result = await enhance_text(
            text, attributes, sender_name, category, channel, auto_enhance
        )
        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="enhance_text",
            service_name="OUTREACH",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
