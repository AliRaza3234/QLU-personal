import traceback
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from qutils.slack.notifications import send_slack_notification
from app.routes.dependancies import get_es_client
from app.models.schemas.company_data import FinancialDataRequest, FinancialDataResponse
from app.utils.company.data.financial_data import get_financial_data

router = APIRouter()


@router.post("/financialdata", response_model=FinancialDataResponse)
async def financialdata(
    request: FinancialDataRequest, es_client=Depends(get_es_client)
):
    """Financial Data"""
    id = request.id
    financial_type = request.financial_type
    request_type = request.type
    return_currency = request.return_currency
    response = {}
    try:
        response = await get_financial_data(
            id, financial_type, request_type, return_currency, es_client
        )
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
            route="financialdata",
            service_name="COMPANY DATA",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})

    return FinancialDataResponse(output=response)
