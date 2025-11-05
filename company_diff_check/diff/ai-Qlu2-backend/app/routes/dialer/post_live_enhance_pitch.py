import traceback
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.models.schemas.dialer.live_pitch import LivePitchRequest, LivePitchResponse
from app.utils.dialer.services.live_pitch.live_pitch import live_pitch_converter
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/live_pitch_converter", response_model=LivePitchResponse)
async def live_enhance(request: LivePitchRequest):
    text = request.text
    try:
        result = await live_pitch_converter(text)
        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="live_pitch_converter",
            service_name="DIALER",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
