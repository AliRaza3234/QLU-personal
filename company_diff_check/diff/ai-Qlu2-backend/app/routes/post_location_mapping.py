from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
import traceback
from qutils.slack.notifications import send_slack_notification

from app.routes.dependancies import get_es_client
from app.models.schemas.location import MapLocationRequest, MapLocationResponse
from app.utils.search.qsearch.location.mapping import location_mapping

router = APIRouter()


@router.post("/location_mapping", response_model=MapLocationResponse)
async def map_full_location(
    request: MapLocationRequest, es_client=Depends(get_es_client)
):
    try:
        locality = request.locality
        locationName = request.locationName
        result = await location_mapping(es_client, locality, locationName)
        result = MapLocationResponse(**result)
        return result
    except Exception as e:
        print("Exception: ", e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="location_mapping",
            service_name="LOCATION MAPPING",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
