import traceback
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.models.schemas.demographics import DemographicsPayload, DemographicsResponse
from app.utils.people.demographics.vision import inference
from app.routes.dependancies import get_es_client
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/demographics", response_model=DemographicsResponse)
async def demo(
    request: DemographicsPayload,
    es_client=Depends(get_es_client),
):
    try:
        payload = request.dict()
        result = await inference(payload, es_client)
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=payload,
            route="/demographics",
            service_name="DEMOGRAPHICS",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
    output = DemographicsResponse(**result)
    return output
