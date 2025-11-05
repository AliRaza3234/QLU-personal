import traceback
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.models.schemas.dialer.generate_category import (
    GenerateCategoryRequest,
    GenerateCategoryResponse,
)
from app.utils.dialer.services.generate_category.get_category import getCategory
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/gen_category", response_model=GenerateCategoryResponse)
async def getnerate_category(req: GenerateCategoryRequest):
    try:
        msg = req.text
        label = await getCategory(msg)
        label = label.replace("category", "Category")
        label = eval(label)
        category = label["Category"].lower()
        return JSONResponse(status_code=200, content={"Category": category})
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=req,
            route="gen_category",
            service_name="DIALER",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
