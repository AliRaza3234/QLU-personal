import traceback
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from app.routes.dependancies import get_es_client
from app.models.schemas.company_data import (
    CompanyOwnershipFilterRequest,
    CompanyOwnershipFilterResponse,
)
from app.utils.company.data.company_ownership_filter import get_company_list
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/company_ownership_filter", response_model=CompanyOwnershipFilterResponse)
async def company_onwership_filter(
    request: CompanyOwnershipFilterRequest, es_client=Depends(get_es_client)
):
    """Financial Data"""
    status = request.status
    filter = request.filter
    try:
        response_data = await get_company_list(status, filter)
        return CompanyOwnershipFilterResponse(output=response_data)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="company_ownership_filter",
            service_name="COMPANY DATA",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
