from fastapi import APIRouter, HTTPException, Depends
import traceback
from app.routes.dependancies import get_es_client
from app.utils.company.products.main import company_products_list
from app.models.schemas.company_data import ProductsRequest, ProductsResponse
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/products", response_model=ProductsResponse)
async def company_products(request: ProductsRequest, es_client=Depends(get_es_client)):
    universalName = request.universalName
    try:
        result = await company_products_list(universalName, es_client)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        else:
            return ProductsResponse(**result)
    except HTTPException as http_exc:
        print(http_exc)
        raise http_exc
    except Exception as e:
        print(e)
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="products",
            service_name="COMPANY DATA",
        )
        raise HTTPException(status_code=500, detail="Internal server error")
