import traceback
from fastapi.responses import JSONResponse
from fastapi import APIRouter, HTTPException, Depends
from app.routes.dependancies import get_es_client
from qutils.slack.notifications import send_slack_notification

from app.utils.company.data.cb_url import get_cb_url as get_cb
from app.models.schemas.company_data import CbUrlResponse

router = APIRouter()


@router.get("/get_cb_url", response_model=CbUrlResponse)
async def get_cb_url(li_universalname, es_client=Depends(get_es_client)):
    try:
        response = await get_cb(li_universalname, es_client)
    except HTTPException as http_exc:
        if http_exc.status_code == 404:
            return CbUrlResponse(cb_url=None)
        return JSONResponse(
            status_code=http_exc.status_code, content={"message": http_exc.detail}
        )
    except Exception as e:
        print(e)
        traceback.print_exc()

        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=li_universalname,
            route="get_cb_url",
            service_name="COMPANY DATA",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
    return CbUrlResponse(cb_url=response)
