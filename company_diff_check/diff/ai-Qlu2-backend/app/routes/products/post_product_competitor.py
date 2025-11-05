import traceback
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.utils.search.aisearch.product.generation.products import (
    get_product_competitors,
)
from app.models.schemas.products.product_competitor import CompetitorRequest
from qutils.slack.notifications import send_slack_notification

from fastapi import Depends
from app.routes.dependancies import get_es_client, get_mysql_pool, get_redis_client


router = APIRouter()


@router.post("/product_competitors")
async def product_competitors(
    request: CompetitorRequest,
    es_client=Depends(get_es_client),
    mysql_pool=Depends(get_mysql_pool),
    redis_client=Depends(get_redis_client),
):
    product_name = request.product_name
    product_identifier = request.product_identifier
    company_name = request.company_name
    company_identifier = request.company_identifier
    try:
        response = await get_product_competitors(
            product_name,
            product_identifier,
            company_name,
            company_identifier,
            es_client,
            mysql_pool,
            redis_client,
        )
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
            route="product_competitors",
            service_name="PRODUCTS",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
