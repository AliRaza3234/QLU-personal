import traceback
from fastapi.responses import JSONResponse
from app.routes.dependancies import get_es_client
from fastapi import APIRouter, HTTPException, Depends
from qutils.slack.notifications import send_slack_notification
from app.utils.company.data.merger_and_acquisitions import (
    get_merger_and_acquisitions,
)
from app.models.schemas.company_data import (
    MergerAcquisitionsRequest,
    MergerAcquisitionsResponse,
)

router = APIRouter()


@router.post("/merger_and_acquisitions", response_model=MergerAcquisitionsResponse)
async def merger_and_acquisitions(
    request: MergerAcquisitionsRequest, es_client=Depends(get_es_client)
):
    cb_url = request.cb_url
    try:
        response = await get_merger_and_acquisitions(cb_url, es_client)

    except HTTPException as http_exc:
        if http_exc.status_code == 404:
            return MergerAcquisitionsResponse(output=None)
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
            route="merger_and_acquisitions",
            service_name="COMPANY DATA",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
    return MergerAcquisitionsResponse(output=response)
