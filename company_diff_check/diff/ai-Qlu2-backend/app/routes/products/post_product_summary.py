import traceback
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.utils.search.aisearch.product.summary.main import generate_summary
from app.models.schemas.products.product_summary import SummaryRequest
from qutils.slack.notifications import send_slack_notification

from fastapi import Depends
from app.routes.dependancies import get_es_client

router = APIRouter()


@router.post("/product_summary")
async def product_summary(request: SummaryRequest, es_client=Depends(get_es_client)):
    product_identifier = request.product_identifier
    product_name = request.product_name
    company_identifier = request.company_identifier
    company_name = request.company_name
    try:
        response = await generate_summary(
            product_identifier,
            product_name,
            company_identifier,
            company_name,
            es_client,
        )
        if response == None:
            return {"summary": "No summary available"}
        return response
    except Exception as e:
        print("Exception: ", e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="product_summary",
            service_name="PRODUCTS",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
