from fastapi import APIRouter
import traceback
from qutils.slack.notifications import send_slack_notification
from fastapi.responses import JSONResponse
from app.models.schemas.outreach.generate_information import (
    generateInfomrationRequest,
    generateInformationResponse,
)

import asyncio

from app.utils.outreach.utils.gpt_utils.gpt_utils import (
    information_extractor,
    getSenderName,
    checkEducation,
    personalization_checker_v2,
)

router = APIRouter()


@router.post("/gen_information", response_model=generateInformationResponse)
async def gen_information(data: generateInfomrationRequest):
    reference = data.reference
    profileData = data.profileData
    try:

        tasks = [
            information_extractor(reference, profileData),
            personalization_checker_v2(reference),
            getSenderName(reference),
            checkEducation(reference),
        ]

        (
            (companies, links, contact),
            personalization_checker_response,
            senderName,
            isEducation,
        ) = await asyncio.gather(*tasks)

        isEducation = isEducation.get("flag", False)

        placeholder_text = personalization_checker_response.get(
            "placeholder_text", reference
        )
        isPersonalised = personalization_checker_response.get("isPersonalized", False)

        senderName = senderName["sender_name"]
        senderName = senderName.strip()
        senderName = senderName.strip("'")
        senderName = senderName.strip('"')

        if "[" in senderName and "]" in senderName:
            senderName = ""

        if isinstance(isPersonalised, str):
            if isPersonalised.lower() == "true":
                isPersonalised = True
            elif isPersonalised.lower() == "false":
                isPersonalised = False

        content = {
            "companies": companies,
            "links": links,
            "contact": contact,
            "placeholderReference": placeholder_text,
            "isPersonalised": isPersonalised,
            "senderName": senderName,
            "isEducation": isEducation,
        }

        return JSONResponse(status_code=200, content=content)
    except Exception as e:
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=data,
            route="gen_information",
            service_name="OUTREACH",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
