import traceback
from qutils.slack.notifications import send_slack_notification
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.utils.company.business_units.get_bu_summary import get_business_unit_summary

from app.models.schemas.businessunits import BusinessUnitsPayload


router = APIRouter()


@router.post("/bu_summary")
async def get_summary_bu(request: BusinessUnitsPayload):
    try:
        result = await get_business_unit_summary(
            request.universal_name, request.business_unit
        )
        return result

    except Exception as e:
        print(e)
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="bu_summary",
            service_name="BUSINESS UNITS",
        )
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
