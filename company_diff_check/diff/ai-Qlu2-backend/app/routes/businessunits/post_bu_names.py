import traceback

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.utils.company.business_units.get_bu_names import busniess_units_names
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/bu_names")
async def get_business_units_names(company_name: str):
    try:
        result = await busniess_units_names(str(company_name))
        return result

    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=company_name,
            route="bu_names",
            service_name="BUSINESS UNITS",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
