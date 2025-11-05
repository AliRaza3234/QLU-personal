import traceback
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from app.routes.dependancies import get_es_client
from app.utils.company.data.stocks import company_stocks
from qutils.slack.notifications import send_slack_notification
from app.models.schemas.company_data import CompanyStocksRequest, CompanyStocksResponse

router = APIRouter()


@router.post("/stocks", response_model=CompanyStocksResponse)
async def stocks(request: CompanyStocksRequest, es_client=Depends(get_es_client)):
    """Stocks"""

    id = request.id
    return_currency = request.return_currency
    response = {}
    try:
        response = await company_stocks(id, return_currency, es_client)
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
            route="stocks",
            service_name="COMPANY DATA",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
    return CompanyStocksResponse(output=response)
