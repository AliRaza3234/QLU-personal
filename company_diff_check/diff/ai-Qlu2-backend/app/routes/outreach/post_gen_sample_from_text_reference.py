from fastapi import APIRouter, HTTPException
import traceback

from qutils.slack.notifications import send_slack_notification

from fastapi.responses import JSONResponse
from app.models.schemas.outreach.generate_text_from_reference import (
    generateSampleRequest,
    generateTextResponse,
)
from app.utils.outreach.services.sample_campaign.generate_sample import *

router = APIRouter()


@router.post("/gen_sample_text", response_model=generateTextResponse)
async def generate_message_from_text_reference(data: generateSampleRequest):
    text = data.text
    reference = data.reference
    category = data.category
    profileData = data.profileData
    channel = data.channel
    sender_name = data.sender_name
    receiver_name = data.receiver_name
    subject = data.subject
    try:
        if channel != "call":
            result = await generate_sample_text(
                reference, category, profileData, channel, sender_name, subject
            )
        else:
            result = await generate_sample_pitch(
                reference, category, profileData, channel, sender_name, subject
            )
        if result.get("message", {}).get("text"):
            result["message"]["text"] = result["message"]["text"].strip("\n")
        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=data,
            route="gen_sample_text",
            service_name="OUTREACH",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
