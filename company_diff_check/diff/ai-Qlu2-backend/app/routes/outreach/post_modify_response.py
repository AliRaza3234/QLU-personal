from fastapi import APIRouter, HTTPException
import traceback
from qutils.slack.notifications import send_slack_notification
from fastapi.responses import JSONResponse
from app.models.schemas.outreach.modify_text import (
    ModifyTextRequest,
    ModifyTextResponse,
)
from app.utils.outreach.services.modify_text.modification import modify_text

router = APIRouter()


@router.post("/modify_response", response_model=ModifyTextResponse)
async def modify_gpt_response(request: ModifyTextRequest):
    text = request.text
    mod_type = request.mod_type
    sender_name = request.sender_name
    receiver_name = request.receiver_name
    channel = request.channel
    try:
        result = await modify_text(text, mod_type, sender_name, receiver_name, channel)
        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="modify_response",
            service_name="OUTREACH",
        )

        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
