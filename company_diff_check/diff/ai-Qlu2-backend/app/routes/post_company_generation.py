import traceback
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse

from qutils.slack.notifications import send_slack_notification

from app.routes.dependancies import get_es_client, get_redis_client, get_mysql_pool
from app.models.schemas.company_generation import CompanyGenerationRequest
from app.utils.search.aisearch.product.generation.products import (
    get_all_products as aisearch_product,
    generate_products_stream,
)
from app.utils.search.aisearch.company.generation.main import generate


router = APIRouter()


@router.post("/generatecompanies")
async def generatecompanies(
    request: CompanyGenerationRequest,
    es_client=Depends(get_es_client),
    mysql_pool=Depends(get_mysql_pool),
    redis_client=Depends(get_redis_client),
):
    """Generate companies based on the text and context"""
    current_prompt = request.current_prompt
    past_prompt = request.past_prompt
    prompt = request.prompt
    context = request.context
    companies = request.companies
    agent = request.agent
    userquery = request.userquery
    employee_count = request.employee_count
    company_ownership = request.company_ownership
    product_filter = request.product_filter
    try:
        if agent == "dual":
            return StreamingResponse(
                generate(
                    current_prompt,
                    past_prompt,
                    es_client,
                    context,
                    userquery,
                    employee_count,
                    company_ownership,
                    mysql_pool,
                    redis_client,
                    product_filter,
                ),
                media_type="text/event-stream",
            )
        elif agent == "product_filter":
            return StreamingResponse(
                generate_products_stream(prompt, es_client, mysql_pool, redis_client),
                media_type="text/event-stream",
            )
        elif agent == "product_aisearch":
            response = await aisearch_product(userquery, prompt, companies)
            return response

    except Exception as e:
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="generatecompanies",
            service_name="COMPANY GENERATION",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
