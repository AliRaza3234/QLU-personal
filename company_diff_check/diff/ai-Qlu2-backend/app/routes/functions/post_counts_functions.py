import traceback
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.routes.dependancies import get_es_client
from app.models.schemas.functions import FunctionsCountPayload, FunctionsCountResponse
from app.utils.people.gfr.functions_counts import get_functions_counts
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/function_counts", response_model=FunctionsCountResponse)
async def function_counter(
    request: FunctionsCountPayload, es_client=Depends(get_es_client)
):
    try:
        payload = request.model_dump()
        result = await get_functions_counts(payload, es_client)
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="function_counts",
            service_name="FUNCTIONS",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
    output = FunctionsCountResponse(**{"output": result})
    return output
