import traceback
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from qutils.slack.notifications import send_slack_notification
from app.routes.dependancies import get_es_client
from app.utils.people.salary.legacy_salary import (
    sec_url_scraping as company_report_link,
)
from app.models.schemas.company_data import (
    CompanyReportLinkInput,
    CompanyReportLinkOutput,
)

router = APIRouter()


def get_latest_date(response):
    for key, value in response.items():
        if type(value) == list:
            latest_date = ""
            final_form = ""
            for link in value:
                date = link.split("/")[-1].split("-")[-1][:-4]
                if latest_date == "":
                    latest_date = date
                    final_form = link
                if latest_date < date:
                    latest_date = date
                    final_form = link
            response[key] = final_form


@router.post("/reports", response_model=CompanyReportLinkOutput)
async def company_report_link_api(
    request: CompanyReportLinkInput, es_client=Depends(get_es_client)
):
    company_name = request.universalName
    output = {}
    try:
        output = await company_report_link(company_name, es_client)
        get_latest_date(output)

        if "message" in output:
            return JSONResponse(status_code=404, content=output)
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="reports",
            service_name="COMPANY DATA",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})

    return CompanyReportLinkOutput(**output)
