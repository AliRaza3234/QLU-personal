import json
import traceback
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.utils.search.aisearch.company.evaluation.company_evaluation import (
    main as company_evaluation,
    keypoint_checking as verify_prompt,
)
from app.models.schemas.company_evaluation import (
    CompanyEvaluationRequest,
    VerifyRequest,
)
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/company_evaluation")
async def evaluate_companies(request: CompanyEvaluationRequest):
    """Evaluate Companies from websearch"""
    prompt = request.prompt
    company = request.company
    try:
        result = json.loads(await company_evaluation(prompt, company))
        return JSONResponse(content=result)
    except Exception as e:
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="company_evaluation",
            service_name="COMPANY EVALUATION",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})


@router.post("/verify_evaluation_request")
async def verify_request(request: VerifyRequest):
    """Evaluate The prompt for company evaluation"""
    prompt = request.prompt
    try:
        result = json.loads(await verify_prompt(prompt))
        return JSONResponse(content=result)
    except Exception as e:
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="verify_evaluation_request",
            service_name="verify_evaluation_request",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
