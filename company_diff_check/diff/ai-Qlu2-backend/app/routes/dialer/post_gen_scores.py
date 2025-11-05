import traceback
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.utils.dialer.services.generate_scores.get_scores import getScores
from app.models.schemas.dialer.scoring_metrics import ScoreRequest, ScoreResponse
from qutils.slack.notifications import send_slack_notification


router = APIRouter()


@router.post("/gen_scores", response_model=ScoreResponse)
async def scoring_metrics(request: ScoreRequest):
    try:
        msg = request.text.strip()
        # category = req.category

        metrics = request.metrices
        category = "sales pitch"
        if msg in ["", "None", "null", "undefined", "nan", "NaN", "N/A"]:
            return JSONResponse(
                status_code=200, content={"scores": {"message": "Invalid message"}}
            )
        result = await getScores(msg, metrics, category)
        # return JSONResponse(status_code=200, content={"scores": result["scores"], "tooltips": result["tooltips"]})
        return JSONResponse(status_code=200, content={"scores": result["scores"]})
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="gen_scores",
            service_name="DIALER",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
