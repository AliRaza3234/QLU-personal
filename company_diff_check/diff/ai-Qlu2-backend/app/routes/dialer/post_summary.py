import traceback
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.models.schemas.dialer.summary import (
    SummaryGeneratorRequest,
    SummaryGeneratorResponse,
)
from app.utils.dialer.services.call_summary.call_summ import (
    generate_summary_cold_call,
)
from qutils.slack.notifications import send_slack_notification


router = APIRouter()


@router.post("/summary-gen", response_model=SummaryGeneratorResponse)
async def summary_generator(request: SummaryGeneratorRequest):
    transcriptions = request.transcriptions
    try:
        transcriptions = " ".join(transcriptions)
        print("Summary input transcriptions: ", transcriptions)
        generated_summary = ""
        if transcriptions:
            generated_summary = await generate_summary_cold_call(transcriptions)
        print("Generated Summary: ", generated_summary)

        return JSONResponse(status_code=200, content=generated_summary)
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="summary-gen",
            service_name="DIALER",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
