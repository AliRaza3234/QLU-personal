import traceback
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.routes.dependancies import get_es_client
from app.models.schemas.functions import (
    FunctionsProfilesPayload,
    FunctionsProfilesResponse,
)
from app.utils.people.gfr.functions_profiles import get_functions_profiles
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/function_profiles", response_model=FunctionsProfilesResponse)
async def function_profiles(
    request: FunctionsProfilesPayload, es_client=Depends(get_es_client)
):
    try:
        payload = request.model_dump()
        result = await get_functions_profiles(payload, es_client)
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="function_profiles",
            service_name="FUNCTIONS",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
    output = FunctionsProfilesResponse(**{"output": result})
    return output
