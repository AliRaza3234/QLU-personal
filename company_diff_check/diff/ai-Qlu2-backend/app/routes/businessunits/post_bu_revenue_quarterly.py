import traceback

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from qutils.slack.notifications import send_slack_notification
from app.models.schemas.businessunits import BusinessUnitsPayload
from app.utils.company.business_units.get_bu_revenue_quarterly import bu_revenue_quarter

router = APIRouter()


@router.post("/bu_quarter_revenue")
async def get_bu_revenue_quarterly(request: BusinessUnitsPayload):
    try:
        result = await bu_revenue_quarter(request.universal_name, request.business_unit)

        return result

    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="bu_quarter_revenue",
            service_name="BUSINESS UNITS",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
