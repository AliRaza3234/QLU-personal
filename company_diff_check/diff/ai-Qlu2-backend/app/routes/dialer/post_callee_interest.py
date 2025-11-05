import traceback
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.models.schemas.dialer.callee_interest import (
    CalleeInterestRequest,
    CalleeInterestResponse,
)
from app.utils.dialer.services.callee_interest.callee_interest import (
    generate_callee_interest,
)
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/calle_interest_check", response_model=CalleeInterestResponse)
async def gen_custom_pitch(request: CalleeInterestRequest):
    callee_data = request.callee_transcription
    caller_data = request.caller_transcription
    try:
        result = await generate_callee_interest(
            caller_data=caller_data, callee_data=callee_data
        )
        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="callee_interest_check",
            service_name="dialer",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
