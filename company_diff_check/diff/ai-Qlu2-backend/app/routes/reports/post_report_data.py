from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.routes.dependancies import get_es_client
from fastapi import Depends
import time
from qutils.slack.notifications import send_slack_notification
import traceback

from app.models.schemas.reports.report_data import (
    ReportYearsRequest,
    ReportYearsResponse,
)
from app.utils.company.reports.services.report_data import get_report_data

router = APIRouter()


@router.post("/filings", response_model=ReportYearsResponse)
async def report_summary(
    request: ReportYearsRequest,
    es_client=Depends(get_es_client),
):

    try:

        result = await get_report_data(request.li_universal_name, es_client)
        if "error" in result:

            return JSONResponse(status_code=200, content={})
        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        print(e)
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="filings",
            service_name="REPORTS",
        )
        raise HTTPException(
            status_code=500, detail=f"Error retrieving blob data: {str(e)}"
        )
