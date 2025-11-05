from fastapi import APIRouter
import asyncio
import traceback
from qutils.slack.notifications import send_slack_notification
from fastapi.responses import JSONResponse
from app.models.schemas.outreach.generate_text_from_reference import (
    generateTextRequest,
    generateTextResponse,
    generateMassTextRequest,
)
from app.utils.outreach.services.dynamic_services.dynamic import (
    generate_msg_from_template,
)

router = APIRouter()


@router.post("/gen_from_text_reference", response_model=generateTextResponse)
async def generate_message_from_text_reference(data: generateTextRequest):
    text = data.text
    reference = data.reference
    category = data.category
    profile_data = data.profileData
    channel = data.channel
    sender_name = data.sender_name
    receiver_name = data.receiver_name
    subject = data.subject
    companies = data.companies
    links = data.links
    contact = data.contact
    profile_summary = data.profileSummary
    is_personalised = data.isPersonalised
    placeholder_reference = data.placeholderReference
    is_education = data.isEducation
    try:
        result = await generate_msg_from_template(
            profile_data["_source"],
            reference,
            channel,
            profile_summary,
            receiver_name,
            is_personalised,
            placeholder_reference,
            is_education,
            subject,
            sender_name,
        )
        if result.get("message", {}).get("text"):
            result["message"]["text"] = result["message"]["text"].strip("\n").strip()
        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=data,
            route="gen_from_text_reference",
            service_name="OUTREACH",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})


@router.post("/mass_gen_from_text_reference", response_model=generateTextResponse)
async def generate_message_from_text_reference(data: generateMassTextRequest):
    text = data.text
    references = data.references
    category = data.category
    profile_data = data.profileData
    channels = data.channels
    sender_names = data.sender_names
    receiver_name = data.receiver_name
    subjects = data.subjects
    companies = data.companies
    links = data.links
    contacts = data.contacts
    profile_summary = data.profileSummary
    is_personalised = data.isPersonalised
    placeholder_references = data.placeholderReferences
    is_education = data.isEducation
    try:
        if len(is_education) == 0:
            is_education = [False] * len(references)
        tasks = []
        for idx in range(len(references)):
            tasks.append(
                generate_msg_from_template(
                    profile_data["_source"],
                    references[idx],
                    channels[idx],
                    profile_summary,
                    receiver_name,
                    is_personalised[idx],
                    placeholder_references[idx],
                    is_education[idx],
                    subjects[idx],
                    sender_names[idx],
                )
            )
        results = await asyncio.gather(*tasks)
        for result in results:
            if result.get("message", {}).get("text"):
                result["message"]["text"] = (
                    result["message"]["text"].strip("\n").strip()
                )
        return JSONResponse(status_code=200, content=results)
    except Exception as e:
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=data,
            route="gen_from_text_reference",
            service_name="OUTREACH",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
