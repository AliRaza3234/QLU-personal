from fastapi import APIRouter
import asyncio
from fastapi.responses import JSONResponse
from app.models.schemas.outreach.summary_generation import (
    SummaryRequest,
    SummaryResponse,
)
from app.utils.outreach.utils.summary_generation.generate_summary import (
    generate_summary,
)
from app.utils.outreach.utils.gpt_utils.gpt_utils import name_normalizer
from qutils.slack.notifications import send_slack_notification
import traceback

router = APIRouter()


@router.post("/summary_generation", response_model=SummaryResponse)
async def summary_generation(req: SummaryRequest):
    profileData = req.profileData
    profileData = profileData["_source"]
    reference_msg = req.reference_message
    try:
        if profileData["fullName"] == "":
            profileName = profileData["firstName"] + " " + profileData["lastName"]
        else:
            profileName = profileData["fullName"]

        tasks = [
            generate_summary(profileData, reference_msg=reference_msg),
            name_normalizer(profileName),
        ]
        summary, profileName = await asyncio.gather(*tasks)

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
            route="summary_generation",
            service_name="OUTREACH",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
