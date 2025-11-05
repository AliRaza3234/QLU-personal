import traceback
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.routes.dependancies import get_es_client
from app.models.schemas.groups import SubgroupCountsPayload, SubgroupCountsResponse
from app.utils.people.gfr.groups_subgroups_counts import get_sg_counts
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/subgroup_counts", response_model=SubgroupCountsResponse)
async def get_subgroup_counts(
    request: SubgroupCountsPayload, es_client=Depends(get_es_client)
):
    try:
        payload = request.model_dump()
        result = await get_sg_counts(payload, es_client)
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="subgroup_counts",
            service_name="GROUPS",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
    output = SubgroupCountsResponse(**{"output": result})
    return output
