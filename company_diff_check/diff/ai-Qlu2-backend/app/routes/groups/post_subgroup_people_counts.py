import traceback
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.models.schemas.groups import (
    SubgroupFunctionAndRankCountsPayload,
    SubgroupFunctionAndRankCountsResponse,
)
from app.routes.dependancies import get_es_client
from app.utils.people.gfr.groups_ranks_counts import get_ranked_ids
from app.utils.people.gfr.groups_functions_counts import get_functional_ids
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post(
    "/subgroup_rank_function_counts",
    response_model=SubgroupFunctionAndRankCountsResponse,
)
async def get_subgroup_rank_function_counts(
    request: SubgroupFunctionAndRankCountsPayload, es_client=Depends(get_es_client)
):
    try:
        payload = request.model_dump()
        if payload["type"] == "rank":
            result = await get_ranked_ids(payload, es_client)
        else:
            result = await get_functional_ids(payload, es_client)
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="subgroup_rank_function_counts",
            service_name="GROUPS",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
    output = SubgroupFunctionAndRankCountsResponse(**{"output": result})
    return output
