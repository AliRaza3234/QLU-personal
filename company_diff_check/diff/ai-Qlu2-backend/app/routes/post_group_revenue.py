from fastapi import APIRouter
from fastapi.responses import JSONResponse
import traceback
from qutils.slack.notifications import send_slack_notification

from app.utils.company.group_revenues.get_group_revenue import groups_to_revenue

router = APIRouter()


@router.post("/group_revenue")
async def get_group_revenue(company_name: str):
    try:
        result = await groups_to_revenue(str(company_name))
        return result
    except Exception as e:
        print("Exception: ", e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload={"company_name": company_name},
            route="group_revenue",
            service_name="GROUP REVENUE",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
