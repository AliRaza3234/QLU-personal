import traceback
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.routes.dependancies import get_es_client
from app.models.schemas.ranks import RanksProfilesPayload, RanksProfilesResponse
from app.utils.people.gfr.ranks_profiles import rank_profiles
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/rank_profiles", response_model=RanksProfilesResponse)
async def rank_profile_counter(
    request: RanksProfilesPayload, es_client=Depends(get_es_client)
):
    try:
        payload = request.model_dump()
        result = await rank_profiles(payload, es_client)
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="rank_profiles",
            service_name="RANKS",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
    output = RanksProfilesResponse(**{"output": result})
    return output
