import traceback
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.utils.search.aisearch.product.generation.products import (
    get_company_products_tab,
)
from app.models.schemas.products.company_products import DataRequest
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/company_products")
async def company_products(request: DataRequest):
    li_universalname = request.li_universalname
    li_name = request.li_name
    es_id = request.es_id
    try:
        response = await get_company_products_tab(li_universalname, li_name, es_id)
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
            route="company_products",
            service_name="PRODUCTS",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
