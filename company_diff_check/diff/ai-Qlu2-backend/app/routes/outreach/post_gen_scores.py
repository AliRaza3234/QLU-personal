from fastapi import APIRouter, HTTPException
import traceback
from qutils.slack.notifications import send_slack_notification
from fastapi.responses import JSONResponse
from app.utils.outreach.services.generate_scores.get_scores import getScores
from app.models.schemas.outreach.scoring_metrics import ScoreRequest, ScoreResponse


router = APIRouter()


@router.post("/gen_scores", response_model=ScoreResponse)
async def scoring_metrics(req: ScoreRequest):
    try:
        msg = req.text
        category = req.category
        metrics = req.metrics
        scores = await getScores(msg, metrics, category)
        return JSONResponse(status_code=200, content={"scores": scores})
    except Exception as e:
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=req,
            route="gen_scores",
            service_name="OUTREACH",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
