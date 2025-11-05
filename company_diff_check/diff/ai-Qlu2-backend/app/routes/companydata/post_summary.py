import traceback
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from app.models.schemas.company_data import (
    FinancialSummaryRequest,
    FinancialSummaryResponse,
)
from app.routes.dependancies import get_es_client
from app.utils.company.data.summary import financial_summary
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/summary", response_model=FinancialSummaryResponse)
async def financialsummary(
    request: FinancialSummaryRequest, es_client=Depends(get_es_client)
):
    """Financial Summary"""
    id = request.id
    return_currency = request.return_currency
    response = {}
    try:
        response = await financial_summary(id, return_currency, es_client)
        if "message" in response:
            message = response["message"]
            return JSONResponse(status_code=400, content={"message": f"{message}"})
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="summary",
            service_name="COMPANY DATA",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
    return FinancialSummaryResponse(output=response)
