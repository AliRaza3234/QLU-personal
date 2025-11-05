from fastapi import APIRouter, HTTPException
import traceback
from qutils.slack.notifications import send_slack_notification
import os
from fastapi.responses import JSONResponse
from app.models.schemas.outreach.sentiment_analysis import (
    SentimentRequest,
    SentimentResponse,
)
from app.utils.outreach.utils.gpt_utils.gpt_utils import sentimentAnalysis

router = APIRouter()

ENV = os.getenv("ENVIRONMENT")


@router.post("/sentiment_analysis", response_model=SentimentResponse)
async def sentiment_analysis(request: SentimentRequest):
    textArr = request.texts
    try:
        sentiment = await sentimentAnalysis(textArr)
        return JSONResponse(status_code=200, content=sentiment)
    except Exception as e:
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="sentiment_analysis",
            service_name="OUTREACH",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
