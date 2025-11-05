import traceback
from app.routes.dependancies import (
    get_es_client,
    get_db_client,
)
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from app.utils.people.similar_profiles.regular.similar import similar_profiles
from app.models.schemas.similar_profiles import (
    SimilarProfilesInput,
    SimilarProfilesOutput,
)
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/similar_profiles", response_model=SimilarProfilesOutput)
async def post_similar_profiles(
    request: SimilarProfilesInput,
    es_client=Depends(get_es_client),
    connector=Depends(get_db_client),
):
    try:
        input_data = request
        result = await similar_profiles(input_data, es_client, connector)

        if "message" in result:
            message = result["message"]
            return JSONResponse(status_code=404, content={"message": f"{message}"})

        profiles = result[0]
        count = result[1]
        return SimilarProfilesOutput(output=profiles, count=count)

    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="similar_profiles",
            service_name="SIMILAR PROFILES",
        )
        raise HTTPException(status_code=500, detail=f"Error occurred: {str(e)}")
