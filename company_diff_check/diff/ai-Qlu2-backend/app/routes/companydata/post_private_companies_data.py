import traceback
from fastapi.responses import JSONResponse
from fastapi import APIRouter, Depends, HTTPException
from app.routes.dependancies import get_es_client
from app.models.schemas.company_data import (
    PrivateCompaniesRequest,
    PrivateCompaniesResponse,
)
from qutils.slack.notifications import send_slack_notification
from app.utils.company.data.funding_rounds import get_funding_rounds

router = APIRouter()


@router.post("/funding_rounds", response_model=PrivateCompaniesResponse)
async def private_companies_financials(
    request: PrivateCompaniesRequest, es_client=Depends(get_es_client)
):
    """Financial Data"""
    cb_url = request.cb_url
    response = {}
    try:
        response = await get_funding_rounds(cb_url, es_client)

    except HTTPException as http_exc:
        if http_exc.status_code == 404:
            return PrivateCompaniesResponse(output=[])
        return JSONResponse(
            status_code=http_exc.status_code, content={"message": http_exc.detail}
        )
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="funding_rounds",
            service_name="COMPANY DATA",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})

    return PrivateCompaniesResponse(output=response)
