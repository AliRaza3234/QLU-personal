import traceback
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.models.schemas.dialer.enhance_pitch import EnhanceRequest, EnhanceResponse
from app.utils.dialer.services.pitch_enhance.enhance_pitch import enhance_pitch
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/voicemail_enhance_pitch", response_model=EnhanceResponse)
async def enhance(
    request: EnhanceRequest,
):
    text = request.text
    metrics = request.metrices
    caller_name = request.caller_name
    callee_name = request.callee_name
    category = "sales pitch"
    try:
        print("post enhance done")
        result = await enhance_pitch(text, metrics, caller_name, callee_name, category)
        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="voicemail_enhance_pitch",
            service_name="DIALER",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
