from fastapi import APIRouter, HTTPException
import traceback

from qutils.slack.notifications import send_slack_notification

from fastapi.responses import JSONResponse
from app.models.schemas.outreach.generate_follow_up_message import (
    FollowupRequest,
    FollowupResponse,
)
from app.utils.outreach.services.sample_campaign.generate_sample import (
    generate_sample_followup,
    generate_sample_followup_pitch,
)

router = APIRouter()


@router.post("/gen_sample_follow_up", response_model=FollowupResponse)
async def generate_follow_up_message(request: FollowupRequest):
    text = request.text
    channel = request.channel
    sender_name = request.sender_name
    receiver_name = request.receiver_name
    reference = request.reference
    profileData = request.profileData
    try:
        if channel != "call":
            result = await generate_sample_followup(
                text, channel, sender_name, receiver_name, reference, profileData
            )
        else:
            result = await generate_sample_followup_pitch(
                text, channel, sender_name, receiver_name, reference, profileData
            )
        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="gen_sample_follow_up",
            service_name="OUTREACH",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
