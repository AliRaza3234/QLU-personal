import traceback
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.models.schemas.reports.report_summary import (
    ReportSummaryRequest,
    ReportSummaryResponse,
)
from app.utils.company.reports.services.report_summary import gen_blob_summary
from app.core.database import cache_data, get_cached_data
from qutils.slack.notifications import send_slack_notification

TABLE_NAME = "company_reports_summary"
router = APIRouter()


@router.post("/summary", response_model=ReportSummaryResponse)
async def report_summary(request: ReportSummaryRequest):

    report_link = request.report_link
    blob_name = request.blob_name
    try:
        result = await get_cached_data(key=blob_name, table=TABLE_NAME)
        if not result:
            result = await gen_blob_summary(
                blob_name=blob_name, report_link=report_link
            )
            if result:
                await cache_data(key=blob_name, value=result, table=TABLE_NAME)

        return JSONResponse(
            status_code=200,
            content={"summary": result},
        )

    except Exception as e:
        print(e)
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="summary",
            service_name="REPORTS",
        )
        raise HTTPException(
            status_code=500, detail=f"Error retrieving blob data: {str(e)}"
        )
