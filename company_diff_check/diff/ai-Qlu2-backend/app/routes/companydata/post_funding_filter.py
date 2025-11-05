import traceback
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from app.routes.dependancies import get_es_client
from app.models.schemas.company_data import (
    FundingFilterRequest,
    FundingFilterResponse,
)
from app.utils.company.data.funding_filter import get_es_id
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/funding_filter", response_model=FundingFilterResponse)
async def funding_filter(
    request: FundingFilterRequest, es_client=Depends(get_es_client)
):
    founded_date_from = request.founded_date_from
    founded_date_to = request.founded_date_to
    last_funding_date_from = request.last_funding_date_from
    last_funding_date_to = request.last_funding_date_to
    last_funding_type = request.last_funding_type
    total_funding_amount_from = request.total_funding_amount_from
    total_funding_amount_to = request.total_funding_amount_to
    last_funding_amount_from = request.last_funding_amount_from
    last_funding_amount_to = request.last_funding_amount_to

    try:
        response_data = await get_es_id(
            founded_date_from,
            founded_date_to,
            last_funding_date_from,
            last_funding_date_to,
            last_funding_type,
            total_funding_amount_from,
            total_funding_amount_to,
            last_funding_amount_from,
            last_funding_amount_to,
            es_client,
        )
        return FundingFilterResponse(output=response_data)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="funding_filter",
            service_name="COMPANY DATA",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
