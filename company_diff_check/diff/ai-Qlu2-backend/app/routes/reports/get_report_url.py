import traceback
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from qutils.slack.notifications import send_slack_notification


from app.models.schemas.reports.reports_url import (
    ReportURLResponse,
)
from app.utils.company.reports.services.get_report_signed_url import get_report_url

router = APIRouter()


@router.get("/get_reports_url", response_model=ReportURLResponse)
async def report_summary(report_blob_name):
    try:
        result = await get_report_url(report_blob_name)
        return ReportURLResponse(signed_url=result)
    except HTTPException as http_exc:
        if http_exc.status_code == 404:
            return ReportURLResponse(signed_url=None)
        return JSONResponse(
            status_code=http_exc.status_code, content={"message": http_exc.detail}
        )
    except Exception as e:
        print(e)
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=report_blob_name,
            route="get_reports_url",
            service_name="REPORTS",
        )
        raise HTTPException(
            status_code=500, detail=f"Error retrieving blob data: {str(e)}"
        )
