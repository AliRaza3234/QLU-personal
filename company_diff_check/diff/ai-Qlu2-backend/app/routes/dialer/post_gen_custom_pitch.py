import traceback
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.models.schemas.dialer.gen_custom_pitch import (
    GenCustomPitchRequest,
    GenCustomPitchResponse,
)
from app.utils.dialer.services.generate_custom_pitch.get_custom_pitch import (
    get_custom_pitch_converter,
)
from qutils.slack.notifications import send_slack_notification


router = APIRouter()


@router.post("/generate_custom_pitch", response_model=GenCustomPitchResponse)
async def gen_custom_pitch(request: GenCustomPitchRequest):
    text = request.text
    callee_name = request.callee_name
    callee_id = request.callee_id
    try:
        result = await get_custom_pitch_converter(text, callee_name)
        result["callee_id"] = callee_id
        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="generate_custom_pitch",
            service_name="DIALER",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
