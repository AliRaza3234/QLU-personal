import traceback
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.models.schemas.groups import (
    SubgroupFunctionAndRankProfilesPayload,
    SubgroupFunctionAndRankProfilesResponse,
)
from app.routes.dependancies import get_es_client
from app.utils.people.gfr.groups_profiles import (
    get_mapped_people_ranks,
)
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post(
    "/subgroup_rank_function_profiles",
    response_model=SubgroupFunctionAndRankProfilesResponse,
)
async def get_subgroup_counts(
    request: SubgroupFunctionAndRankProfilesPayload, es_client=Depends(get_es_client)
):
    try:
        payload = request.model_dump()
        result = await get_mapped_people_ranks(payload, es_client)
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="subgroup_rank_function_profiles",
            service_name="GROUPS",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
    output = SubgroupFunctionAndRankProfilesResponse(**{"output": result})
    return output
