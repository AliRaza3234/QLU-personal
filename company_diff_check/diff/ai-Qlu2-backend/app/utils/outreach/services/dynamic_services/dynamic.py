import json
import os
import asyncio
from elasticsearch import AsyncElasticsearch
from app.utils.outreach.utils.gpt_utils.gpt_runner import gpt_runner
from app.utils.outreach.utils.gpt_utils.gpt_utils import (
    gpt_reduce_length,
    name_normalizer,
    getSenderName,
    checkEducation,
    extract_generic,
    extract_placeholders,
    is_probably_url,
    check_subject_personalization,
)
from app.utils.outreach.utils.summary_generation.generate_summary import (
    generate_summary,
)
from app.utils.outreach.utils.subject_generation.subject_generation import (
    subject_generation,
)

from app.utils.outreach.services.dynamic_services.dynamic_prompts import (
    CONTEXT_PROMPT,
    ENHANCE_HELPER_SYSTEM_PROMPT,
    ENHANCE_SYSTEM_PROMPT,
    ENHANCE_USER_PROMPT,
    ENAHNCE_SYSTEM_GRAMMAR_PROMPT,
    ENHANCE_USER_GRAMMAR_PROMPT,
    MSG_GENERATION_SYSTEM,
    MINIATURE_EMAIL_SYSTEM_PROMPT,
    MINIATURE_TEXT_SYSTEM_PROMPT,
    MINIATURE_SYSTEM_PROMPT,
)

from app.utils.outreach.services.sample_campaign.generate_sample_prompts import (
    PITCH_SAMPLE,
)
from copy import deepcopy
import re
from typing import Dict, Any


GPT_MAIN_MODEL = "gpt-4.1"
GPT_COST_EFFICIENT_MODEL = "gpt-4o-mini"
GPT_BACKUP_MODEL = "gpt-4.1"
ENVIRONMENT = os.getenv("ENVIRONMENT")


async def enhance_text(
    text: str,
    attributes: Dict[str, Any],
    sender_name: str,
    category: str,
    channel: str,
    auto_enhance: bool = False,
) -> Dict[str, Any]:
    """
    Asynchronously enhances a given text based on specified attributes such as flattery, incentives, and call to action,
    for different communication channels. This function constructs a dynamic prompt for an AI model, which then generates
    a more persuasive or engaging message tailored to the receiver's profile.

    Depending on the communication channel (e.g., LinkedIn connect or message), different attributes are emphasized in the
    enhancement process. For example, personalization might be emphasized more heavily in direct messages based on the
    detailed summary of the receiver's profile.

    Parameters:
        text (str): The original text that needs to be enhanced.
        attributes (Dict[str, Any]): A dictionary containing various attributes (flattery, incentive, etc.) that guide
                                     how the text should be enhanced.
        sender_name (str): The name of the sender of the message.
        channel (str): The communication channel ('linkedin_connect', 'linkedin_message', etc.).
        category (str): The label of the message

    Returns:
        Dict[str, Any]: A dictionary containing the enhanced text. The key 'message' includes 'subject' (always None here)
                        and 'text', which is the enhanced message content.

    Raises:
        KeyError: If essential attributes are missing in the input dictionary.
    """

    chat_ = {}

    metrics = attributes["metrics"]
    receiver_data = attributes["receiver_data"]["_source"]
    if receiver_data["fullName"] == "":
        profileName = receiver_data["firstName"] + " " + receiver_data["lastName"]
    else:
        profileName = receiver_data["fullName"]

    callToAction = False
    personalization = False

    if "personalization" in metrics:
        personalization = metrics["personalization"]

    if "Personalization" in metrics:
        personalization = metrics["Personalization"]

    if "Personalisation" in metrics:
        personalization = metrics["Personalisation"]

    if "personalisation" in metrics:
        personalization = metrics["personalisation"]

    if "callToAction" in metrics:
        del metrics["callToAction"]

    if "Call To Action" in metrics:
        del metrics["Call To Action"]
    # callToAction = metrics["callToAction"]

    if auto_enhance:
        tasks = [getSenderName(text), name_normalizer(profileName)]
        senderName, profileName = await asyncio.gather(*tasks)
        system_prompt = deepcopy(ENAHNCE_SYSTEM_GRAMMAR_PROMPT)
        user_prompt = deepcopy(ENHANCE_USER_GRAMMAR_PROMPT)

    else:
        system_prompt = deepcopy(ENHANCE_SYSTEM_PROMPT)
        user_prompt = deepcopy(ENHANCE_USER_PROMPT)

        if personalization:
            tasks = [
                getSenderName(text),
                generate_summary(receiver_data),
                checkEducation(text),
                name_normalizer(profileName),
            ]
            (
                senderName,
                summary_receiver,
                isEducation,
                profileName,
            ) = await asyncio.gather(*tasks)

            isEducation = isEducation["flag"]

            education = receiver_data.get("education", "")
            if isEducation:
                profileEducation = ""
                if education:
                    profileEducation = f"\nTotal Education history of {profileName}:\n"
                    for ed in education:
                        schoolName = ed.get("schoolName", "")
                        start = ed.get("start", "")
                        end = ed.get("end", "")
                        degreeName = ed.get("degreeName", "")
                        fieldOfStudy = ed.get("fieldOfStudy", "")
                        if schoolName:
                            profileEducation += f"School Name: {schoolName}\n"
                        if start:
                            profileEducation += f"Start Date: {start}\n"
                        if end:
                            profileEducation += f"End Date: {end}\n"
                        if degreeName:
                            profileEducation += f"Degree: {degreeName}\n"
                        if fieldOfStudy:
                            profileEducation += f"Field Of Study: {fieldOfStudy}\n"
                summary_receiver += profileEducation

            if "none" not in summary_receiver.lower():
                # print("Adding personalization")
                user_prompt += (
                    "\nAdd more personalized text of the message receiver on the basis of his profile summary: "
                    + summary_receiver
                )

        else:
            profileName, senderName = await asyncio.gather(
                *[name_normalizer(profileName), getSenderName(text)]
            )

        senderName = senderName.get("sender_name", "")
        senderName = senderName.strip()
        senderName = senderName.strip("'")
        senderName = senderName.strip('"')

        if "[" in senderName and "]" in senderName:
            senderName = ""
        if senderName:
            sender_name = senderName

    # if not auto_enhance and callToAction:
    #     user_prompt += f"Add the following call to action: {metrics['callToAction']}\n"
    character_length = len(text) + 200
    if channel == "linkedin_connect":
        character_length = 160
    elif channel == "linkedin_premium":
        character_length = 260
    user_prompt = user_prompt.format(
        text=text,
        sender_name=sender_name,
        reference=character_length,
        category=category,
    )

    if profileName:
        user_prompt += (
            f"\n\nFor reference, the name of the message receiver is {profileName}"
        )
    # metrics = await get_enhance_definitions(metrics)
    # print(f"Final Attributes = {metrics}")
    metrics = {k: v for k, v in metrics.items() if v}
    system_prompt = system_prompt.format(metrics=metrics)

    # print(system_prompt)
    # print(user_prompt)

    chat = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        enhanced_text = await gpt_runner(
            chat=chat, temperature=0.2, model=GPT_MAIN_MODEL
        )
    except Exception as e:
        print(e)
        enhanced_text = await gpt_runner(
            chat=chat, temperature=0.2, model=GPT_BACKUP_MODEL
        )

    if channel == "linkedin_connect" or channel == "linkedin_premium":
        if len(enhanced_text) > character_length + 30:
            loop_count = 0
            while len(enhanced_text) > character_length + 30:
                # print("I AM HERE IN CONNECT", loop_count)
                # print("Rerunning for", len(enhanced_text))
                if loop_count >= 6:
                    break
                enhanced_text, chat_ = await gpt_reduce_length(
                    enhanced_text, character_length, loop_count
                )
                enhanced_text = enhanced_text.replace('"', "")
                loop_count += 1
    # print(enhanced_text)
    if ENVIRONMENT == "development":
        return {
            "message": {
                "subject": None,
                "text": enhanced_text,
                "length": len(enhanced_text),
                "chat": chat_,
            }
        }
    else:
        return {
            "message": {
                "subject": None,
                "text": enhanced_text,
            }
        }


async def generate_msg_from_template(
    profileData: dict,
    reference: str,
    channel: str,
    profile_summary: str,
    profileName: str,
    isPersonalised: bool,
    placeholderReference: str,
    isEducation: bool,
    subject: str = "",
    sender_name: str = "",
) -> Dict[str, Any]:
    """
    Asynchronously generates a message from a template based on the provided profile data, reference, channel, sender name, category, subject, companies, links, contact, profile summary, profile name, is personalised, and placeholder reference.

    This function constructs a dynamic prompt for an AI model, which then generates

    """
    subject_task = None
    if subject and reference:
        subject_task = asyncio.create_task(
            check_subject_personalization(subject, reference)
        )

    character_length = len(reference) + 20
    if channel == "linkedin_connect" or channel == "linkedin_premium":
        character_length = 160 if channel == "linkedin_connect" else 260

    placeholders = extract_placeholders(placeholderReference)
    placeholders = [p for p in placeholders if not is_probably_url(p)]

    if len(placeholders) == 1:
        if "name" in placeholders[0].lower():
            isPersonalised = False
    elif len(placeholders) > 0 and not isPersonalised:
        isPersonalised = True

    if "none" in profile_summary.lower():
        profile_summary = f"Receiver Name: {profileName}"
        isPersonalised = False

    if isPersonalised:

        if isEducation:
            education = profileData.get("education", "")
            profileEducation = ""
            if education:
                profileEducation = f"\nTotal Education history of {profileName}:\n"
                for ed in education:
                    schoolName = ed.get("schoolName", "")
                    start = ed.get("start", "")
                    end = ed.get("end", "")
                    degreeName = ed.get("degreeName", "")
                    fieldOfStudy = ed.get("fieldOfStudy", "")
                    if schoolName:
                        profileEducation += f"School Name: {schoolName}\n"
                    if start:
                        profileEducation += f"Start Date: {start}\n"
                    if end:
                        profileEducation += f"End Date: {end}\n"
                    if degreeName:
                        profileEducation += f"Degree: {degreeName}\n"
                    if fieldOfStudy:
                        profileEducation += f"Field Of Study: {fieldOfStudy}\n"
            profile_summary += profileEducation

    system_prompt = deepcopy(MSG_GENERATION_SYSTEM)
    if isPersonalised:
        user_prompt = f"""<reference_msg> {placeholderReference} </reference_msg>\n<receiver_data> Name: {profileName}, Profile Summary: {profile_summary} </receiver_data>"""
    else:
        user_prompt = f"""<reference_msg> {placeholderReference} </reference_msg>\n<receiver_data> Name: {profileName} </receiver_data>"""

    if channel == "linkedin_connect" or channel == "linkedin_premium":
        system_prompt += f"\n<important>\n-The Final message must not exceed {character_length+30} characters\n</important>"

    chat = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    if ENVIRONMENT == "production" or ENVIRONMENT == "staging":
        outreach_text = await gpt_runner(chat=chat, temperature=0.2, model="gpt-4.1")
    else:
        outreach_text = await gpt_runner(
            chat=chat, temperature=0.2, model="gpt-oss-120b", provider="groq"
        )

    if "[" in outreach_text and "]" in outreach_text:
        placeholders = extract_placeholders(outreach_text)
        if any(not is_probably_url(p) for p in placeholders):
            chat.append({"role": "assistant", "content": outreach_text})
            chat.append(
                {
                    "role": "user",
                    "content": "There seems to be a placeholder in the text. Please remove it and handle it gracefully. Follow the output format.",
                }
            )
            outreach_text = await gpt_runner(
                chat=chat, temperature=0.2, model="gpt-4.1"
            )

    outreach_text = extract_generic(
        "<outreach_text>", "</outreach_text>", outreach_text
    )

    if channel == "linkedin_connect" or channel == "linkedin_premium":
        if len(outreach_text) > character_length + 39:

            loop_count = 0
            while len(outreach_text) > character_length + 39:

                if loop_count >= 6:
                    break
                outreach_text, chat_ = await gpt_reduce_length(
                    outreach_text, character_length, loop_count
                )
                outreach_text = outreach_text.replace('"', "")
                loop_count += 1

    if channel == "email":
        if subject_task:
            is_subject_personalized, placeholder_subject = await subject_task
            subject = placeholder_subject
        else:
            is_subject_personalized = True
        subject = await subject_generation(
            outreach_text,
            subject,
            False,
            profile_summary,
            sender_name,
            is_subject_personalized,
        )
        outreach_text = re.sub(r"^Subject:.*\n", "", outreach_text, flags=re.MULTILINE)

    result = {"message": {"subject": subject, "text": outreach_text}}
    return result


async def generate_pitch(
    profileData: dict,
    reference: str,
    sender_name: str,
    category: str,
    profile_summary: str,
    profileName: str,
    isPersonalised: bool,
    placeholderReference: str,
) -> Dict[str, Any]:
    """
    Async Function to generate message using a reference message and user profile data which
    will be used to generate profile summary.

    Args:
    - reference (str): Reference message
    - category (str): Intent of the message
    - profileData (dict): Dictionary object of receiver's profile
    - channel (str): Channel of message (LinkedIn, email etc)
    - sender_name (str): Name of the message sender
    - subject (str): Reference subject

    Returns:
    - dictionary: Message and Subject if applicable
    """
    position = ""
    tasks = []

    if category == "recruiting" or category == "recruitment":
        user_context_prompt = deepcopy(reference)
        system_prompt = CONTEXT_PROMPT

        tasks.append(
            gpt_runner(
                chat=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_context_prompt},
                ],
                temperature=0.2,
                model="gpt-4o-mini",
                json_format=True,
            )
        )

        res = await asyncio.gather(*tasks)

        res = json.loads(res[0])
        if res["position"]:
            position += "\n".join(res["position"])

    reference = placeholderReference

    user_prompt = ""

    system_prompt_text = deepcopy(MSG_GENERATION_SYSTEM)
    if isPersonalised:
        if "none" not in profile_summary.lower():
            user_prompt = f"""
            <reference_outreach_text> {reference} </reference_outreach_text>
            <receiver_info> {profile_summary} </receiver_info>
            <sender_name> {sender_name} </sender_name>"""
    if not user_prompt:
        user_prompt = f"""
            <reference_outreach_text> {reference} </reference_outreach_text>
            <receiver_info> {profileName} </receiver_info>
            <sender_name> {sender_name} </sender_name>"""

    if position:
        user_prompt += f"\nJob Position(s) referred in reference: {position}"

    system_prompt_text += "\nIf there are any placeholders in the reference message given, fill them meaningfully from the information provided. The final message you generate must not contain any placeholders"

    chat = [
        {"role": "system", "content": system_prompt_text},
        {"role": "user", "content": user_prompt},
    ]
    try:
        outreach_text = await gpt_runner(model="gpt-4.1", temperature=0.2, chat=chat)
    except Exception as e:
        print(e)
        outreach_text = await gpt_runner(model="gpt-4.1", temperature=0.2, chat=chat)

    outreach_text = extract_generic(
        "<outreach_text>", "</outreach_text>", outreach_text
    )

    return {"message": {"subject": None, "text": outreach_text}}


async def get_miniature_round(
    call_pitch: str, channel: str, es_id: str, es_client: AsyncElasticsearch
):
    # profile_data = await get_profile_data(es_id, es_client)
    # profile_summary = await generate_summary(profile_data)

    system_prompt = (
        deepcopy(MINIATURE_SYSTEM_PROMPT)
        # if channel == "email"
        # else deepcopy(MINIATURE_TEXT_SYSTEM_PROMPT)
    )
    user_prompt = f"""<call_pitch> {call_pitch} </call_pitch>"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    res = await gpt_runner(chat=messages, temperature=0.2, model="gpt-4.1")

    if channel == "email":
        subject = extract_generic("<subject>", "</subject>", res)
        msg = extract_generic("<follow_up>", "</follow_up>", res)
    else:
        subject = None
        msg = extract_generic("<follow_up>", "</follow_up>", res)

    return {
        "subject": subject.strip().strip("\n") if subject else None,
        "text": msg.strip().strip("\n"),
    }
