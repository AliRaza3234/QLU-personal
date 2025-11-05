import traceback
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from qutils.slack.notifications import send_slack_notification
from app.models.schemas.competitor_companies import CompanyCompetitorsRequest
from app.utils.company.competitors.competitor_company import generate_competitor
from app.routes.dependancies import get_es_client, get_mysql_pool, get_redis_client

router = APIRouter()


@router.post("/company_competitors")
async def company_competitors(
    request: CompanyCompetitorsRequest,
    es_client=Depends(get_es_client),
    mysql_pool=Depends(get_mysql_pool),
    redis_client=Depends(get_redis_client),
):
    """Company Competitors"""
    id = request.id
    try:
        result = await generate_competitor(id, es_client, mysql_pool, redis_client)
        return JSONResponse(content={"output": result})

    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="company_competitors",
            service_name="COMPANY COMPETITORS",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
