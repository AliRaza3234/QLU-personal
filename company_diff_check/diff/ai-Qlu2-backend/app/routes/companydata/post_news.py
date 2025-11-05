import traceback
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from qutils.slack.notifications import send_slack_notification

from app.routes.dependancies import get_es_client
from app.utils.company.data.news import company_news
from app.models.schemas.company_data import CompanyNewsRequest, CompanyNewsResponse

router = APIRouter()


@router.post("/news", response_model=CompanyNewsResponse)
async def companynews(request: CompanyNewsRequest, es_client=Depends(get_es_client)):
    """Company News"""
    id = request.id
    response = {}
    try:
        response = await company_news(id, es_client)

    except HTTPException as http_exc:
        if http_exc.status_code == 404:
            return CompanyNewsResponse(output=[])
        return JSONResponse(
            status_code=http_exc.status_code, content={"message": http_exc.detail}
        )
    except Exception as e:
        print(e)
        traceback.print_exc()

        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="news",
            service_name="COMPANY DATA",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
    return CompanyNewsResponse(output=response)
