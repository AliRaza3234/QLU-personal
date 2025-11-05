from fastapi import Depends
from app.routes.dependancies import get_es_client

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.models.schemas.dialer.prof_summ_gen import (
    ProfileSummaryRequest,
    ProfileSummaryResponse,
)
from app.utils.dialer.utils.prof_summary_generation.generate_prof_summary import (
    generate_summary,
)
from app.utils.dialer.utils.gpt_utils.gpt_utils import name_normalizer
from qutils.qes.es_utils import run_search_query
import traceback
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/profile_summary_generation", response_model=ProfileSummaryResponse)
async def prof_summ_generation(
    req: ProfileSummaryRequest,
    es_client=Depends(get_es_client),
):
    resp = await run_search_query(
        es_client,
        query={"query": {"terms": {"_id": [req.profileEsID]}}},
        index="staging_profiles",
    )
    profileData = resp["_source"]

    try:
        summary = await generate_summary(profileData)
        if profileData["fullName"] == "":
            profileName = profileData["firstName"] + " " + profileData["lastName"]
        else:
            profileName = profileData["fullName"]

        name_data = await name_normalizer(profileName)
        title = ""
        if "Title" in name_data:
            if name_data["Title"]:
                title = name_data["Title"]
        if "firstName" in name_data:
            if name_data["firstName"]:
                profileName = title + " " + name_data["firstName"]
        profileName = profileName.strip()
        profileName = profileName.strip('"')
        profileName = profileName.strip("'")
        return JSONResponse(
            status_code=200,
            content={"profileSummary": summary, "receiverName": profileName},
        )
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=req,
            route="profile_summary_generation",
            service_name="DIALER",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
