import traceback
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.routes.dependancies import get_es_client
from app.models.schemas.ranks import RanksCountPayload, RanksCountResponse
from app.utils.people.gfr.ranks_counts import get_rank_counts
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/rank_counts", response_model=RanksCountResponse)
async def rank_counter(request: RanksCountPayload, es_client=Depends(get_es_client)):
    try:
        payload = request.model_dump()
        result = await get_rank_counts(payload, es_client)
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="rank_counts",
            service_name="RANKS",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
    output = RanksCountResponse(**{"output": result})
    return output
