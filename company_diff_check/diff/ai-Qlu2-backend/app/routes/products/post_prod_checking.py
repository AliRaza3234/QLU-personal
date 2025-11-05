import traceback
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.utils.search.aisearch.product.generation.products import prod_checking_agent
from app.models.schemas.products.product_check import CheckRequest
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/product_check")
async def product_data(request: CheckRequest):
    prompt = request.prompt
    user_query = request.user_query
    try:
        response = await prod_checking_agent(user_query, prompt)
        if response == None:
            return None
        return response
    except Exception as e:
        print("Exception: ", e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="product_check",
            service_name="PRODUCTS",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
