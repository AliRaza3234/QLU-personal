import traceback

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from app.utils.company.business_units.get_bu_trace import trace_bu
from qutils.slack.notifications import send_slack_notification
from app.models.schemas.businessunits import BusinessUnitsTracePayload


router = APIRouter()


@router.post("/bu_trace")
async def get_business_units_names(request: BusinessUnitsTracePayload):
    try:
        result = await trace_bu(
            request.universal_name,
            request.business_unit,
            request.year,
            request.period,
            request.value,
            request.container,
        )

        return result

    except HTTPException as http_exc:
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
            route="bu_trace",
            service_name="BUSINESS UNITS",
        )
        return JSONResponse(
            status_code=500, content={"message": "An internal server error occurred"}
        )
