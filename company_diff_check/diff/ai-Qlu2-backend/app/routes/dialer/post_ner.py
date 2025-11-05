import traceback
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse


from app.models.schemas.dialer.ner import NEROnTextRequest, NEROnTextResponse
from app.utils.dialer.utils.gpt_utils.gpt_utils import ner_on_text
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/ner-text", response_model=NEROnTextResponse)
async def ner(request: NEROnTextRequest):
    text = request.text
    try:
        result = await ner_on_text(text.strip())
        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="ner-text",
            service_name="DIALER",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
