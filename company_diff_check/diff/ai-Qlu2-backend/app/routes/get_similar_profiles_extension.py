import traceback
from app.routes.dependancies import (
    get_es_client,
    get_db_client,
)
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from app.utils.people.similar_profiles.extension.similar import similar_profiles
from app.models.schemas.similar_profiles_extension import (
    SimilarProfilesInput,
    SimilarProfilesOutput,
)
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.get("/similar_profiles_extension", response_model=SimilarProfilesOutput)
async def get_similar_profiles(
    esId: str = Query(..., description="Elasticsearch ID of the profile"),
    type: str = Query(..., description="Type of the profile"),
    offset: int = Query(..., description="Offset for pagination"),
    limit: int = Query(..., description="Offset for pagination"),
    es_client=Depends(get_es_client),
    connector=Depends(get_db_client),
):
    try:
        input_data = SimilarProfilesInput(
            esId=esId, type=type, offset=offset, limit=limit
        )
        result = await similar_profiles(input_data, es_client, connector)
        if "message" in result:
            message = result["message"]
            return JSONResponse(status_code=404, content={"message": f"{message}"})
    except Exception as e:
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload={"esId": esId, "type": type, "offset": offset, "limit": limit},
            route="similar_profiles_extension",
            service_name="SIMILAR PROFILES",
        )
        raise HTTPException(status_code=500, detail=f"Error occurred: {str(e)}")
    return SimilarProfilesOutput(output=result)
