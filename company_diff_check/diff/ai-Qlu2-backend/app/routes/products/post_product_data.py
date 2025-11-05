import traceback
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.utils.search.aisearch.product.generation.products import get_product_data
from app.models.schemas.products.product_data import DataRequest
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/product_data")
async def product_data(request: DataRequest):
    product_identifier = request.product_identifier
    try:
        response = await get_product_data(product_identifier)
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
            route="product_data",
            service_name="PRODUCTS",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
