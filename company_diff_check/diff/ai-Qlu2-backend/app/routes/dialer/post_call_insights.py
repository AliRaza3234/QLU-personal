import traceback
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.models.schemas.dialer.post_call_insights import (
    PostCallInsightsRequest,
    PostCallInsightsResponse,
)
from app.utils.dialer.services.post_call_insights.call_insight import (
    get_callee_interest,
    get_callee_follow_up,
    get_pitch_usage,
)
from qutils.slack.notifications import send_slack_notification
from asyncio import gather

router = APIRouter()


@router.post("/post-call-insights", response_model=PostCallInsightsResponse)
async def post_call_insights(request: PostCallInsightsRequest):
    transcriptions = request.transcriptions
    pitch = request.pitch

    try:
        if transcriptions:
            callee_interest_task = get_callee_interest(transcriptions)
            callee_followup_task = get_callee_follow_up(transcriptions)
            tasks = [callee_interest_task, callee_followup_task]

            if pitch:
                pitch_usage_task = get_pitch_usage(transcriptions, pitch)
                tasks.append(pitch_usage_task)

            results = await gather(*tasks)

            callee_interest = results[0]
            callee_followup = results[1]
            is_pitched = results[2] if pitch else False

            result = {
                "isInterested": callee_interest,
                "isFollowup": callee_followup,
                "isPitched": is_pitched,
            }

            return JSONResponse(status_code=200, content=result)
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="post-call-insights",
            service_name="DIALER",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
