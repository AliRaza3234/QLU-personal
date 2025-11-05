from copy import deepcopy
import json
import re
import asyncio
from typing import List, Dict, Any, Union
from dotenv import load_dotenv
from app.utils.outreach.services.dynamic_services.dynamic_prompts import CONTEXT_PROMPT
from app.utils.outreach.utils.gpt_utils.gpt_runner import gpt_runner
from app.utils.outreach.utils.gpt_utils.gpt_utils import (
    information_extractor,
    personalisation_checker,
    name_normalizer,
    getSenderName,
    gpt_reduce_length,
    checkEducation,
    personalization_remover,
    extract_generic,
    extract_placeholders,
    is_probably_url,
    personalization_checker_v2,
)
from app.utils.outreach.utils.summary_generation.generate_summary import (
    generate_summary,
)
from app.utils.outreach.utils.subject_generation.subject_generation import (
    subject_generation,
)
from app.utils.outreach.utils.context_utils.context_utils import (
    rerunning_for_context,
    evaluate_context,
)
from app.utils.outreach.services.sample_campaign.generate_sample_prompts import (
    SAMPLE_MESSAGE_PROMPT,
    FOLLOW_UP_EMAIL_SYSTEM_PROMPT,
    FOLLOW_UP_EMAIL_USER_PROMPT,
    FOLLOW_UP_LI_SYSTEM_PROMPT,
    FOLLOW_UP_LI_USER_PROMPT,
    FOLLOW_UP_LICONNECT_SYSTEM_PROMPT,
    FOLLOW_UP_LICONNECT_USER_PROMPT,
    FOLLOW_UP_LI_PERSONALISED_SYSTEM_PROMPT,
    FOLLOW_UP_LI_PERSONALISED_USER_PROMPT,
    FOLLOW_UP_EMAIL_PERSONALISED_SYSTEM_PROMPT,
    FOLLOW_UP_EMAIL_PERSONALISED_USER_PROMPT,
    FOLLOW_UP_LICONNECT_PERSONALISED_SYSTEM_PROMPT,
    FOLLOW_UP_LICONNECT_PERSONALISED_USER_PROMPT,
    PITCH_SAMPLE,
    PITCH_SAMPLE_FOLLOWUP,
)

import os

load_dotenv()

ENV = os.getenv("ENVIRONMENT")


async def generate_sample_text(
    reference: str,
    category: str,
    profileData_Original: Dict[str, Any],
    channel: str,
    sender_name: str,
    subject: str,
) -> Dict[str, Any]:

    chat_ = {}

    if channel == "email" or channel == "linkedin_message":
        character_length = "None"
    else:
        character_length = 200 if channel == "linkedin_connect" else 300

    profileData = profileData_Original["_source"]

    actual_reference = reference

    if profileData["fullName"] == "":
        profileName = profileData["firstName"] + " " + profileData["lastName"]
    else:
        profileName = profileData["fullName"]

    tasks = [
        personalization_checker_v2(actual_reference),
        # personalization_remover(actual_reference),
        checkEducation(reference),
        name_normalizer(profileName),
        generate_summary(profileData, True, reference),
        # personalisation_checker(actual_reference),
        information_extractor(actual_reference),
        getSenderName(actual_reference),
    ]

    (
        personalization_checker_v2_response,
        isEducation,
        profileName,
        profile_summary,
        (companies, links, contact),
        senderName,
    ) = await asyncio.gather(*tasks)

    isPersonalised = personalization_checker_v2_response["isPersonalized"]
    placeholder_reference = personalization_checker_v2_response["placeholder_text"]

    isEducation = isEducation["flag"]

    education = profileData.get("education", "")

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
        profile_summary += profileEducation

    senderName = senderName["sender_name"]
    senderName = senderName.strip()
    senderName = senderName.strip("'")
    senderName = senderName.strip('"')

    if "[" in senderName and "]" in senderName:
        senderName = ""
    if senderName:
        sender_name = senderName

    placeholders = extract_placeholders(placeholder_reference)
    placeholders = [p for p in placeholders if not is_probably_url(p)]

    if len(placeholders) == 1:
        if "name" in placeholders[0].lower() and isPersonalised:
            isPersonalised = False
    # elif len(placeholders) > 0 and not isPersonalised:
    #     isPersonalised = True

    if "none" in profile_summary.lower():
        isPersonalised = False

    receiver_details = (
        f"<receiver_details> {profile_summary} </receiver_details>"
        if isPersonalised
        else f"<receiver_name> {profileName} </receiver_name>"
    )

    channel_map = {
        "email": "Email",
        "linkedin_connect": "Linkedin Connect",
        "linkedin_premium": "Linkedin Premium",
        "linkedin_message": "Linkedin Message",
    }

    system_prompt = deepcopy(SAMPLE_MESSAGE_PROMPT)
    user_prompt = f"""<sample_message> {placeholder_reference} </sample_message>
    <is_personalized> {isPersonalised} </is_personalized>
    <sender_name> {sender_name} </sender_name>
    {receiver_details}
    <channel> {channel_map[channel]} </channel>
    <character_limit> {character_length} </character_limit>"""

    if links:
        user_prompt += f"<Important_Links> {links} </Important_Links>"
    if companies:
        user_prompt += f"<Important_Companies> {companies} </Important_Companies>"
    if contact:
        user_prompt += f"<Important_Contact> {contact} </Important_Contact>"

    chat = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    res = await gpt_runner(model="gpt-4.1", temperature=0.2, chat=chat)

    outreach_text = extract_generic("<message>", "</message>", res)
    outreach_text = outreach_text.replace('"', "")

    if channel == "email":
        subject = extract_generic("<email_subject>", "</email_subject>", res)
        result = {"message": {"subject": subject, "text": outreach_text}}
        return result
    elif (channel == "linkedin_connect" or channel == "linkedin_premium") and len(
        outreach_text
    ) > character_length:
        loop_count = 0
        while len(outreach_text) > character_length:
            if loop_count >= 6:
                break
            outreach_text, chat_ = await gpt_reduce_length(
                outreach_text, character_length, loop_count
            )
            outreach_text = outreach_text.replace('"', "")
            loop_count += 1
    if ENV == "development":
        return {
            "message": {
                "subject": None,
                "text": outreach_text,
                "length": len(outreach_text),
                "chat": chat_,
            }
        }
    else:
        return {
            "message": {
                "subject": None,
                "text": outreach_text,
            }
        }


async def generate_sample_followup(
    texts: List[str],
    channel: str,
    sender_name: str,
    receiver_name: str,
    reference: str,
    profileData: dict,
) -> Dict[str, Union[None, Dict[str, str]]]:
    """
    Asynchronously generates a follow-up message tailored to the communication channel and the involved parties.

    This function utilizes predefined system and user prompts, which are formatted with specific details such as
    the text to be followed up on, and the sender and receiver names. It adapts the message creation process based
    on the channel of communication (email, LinkedIn connection, or LinkedIn message). If necessary, the message
    length is adjusted to meet platform-specific restrictions, particularly for LinkedIn connections.

    Parameters:
        text (List[str]): The original text or context for the follow-up message.
        channel (str): The communication channel ('email', 'linkedin_connect', or 'linkedin_message').
        sender_name (str): The name of the sender of the message.
        receiver_name (str): The name of the recipient of the message.

    Returns:
        Dict[str, Union[None, Dict[str, str]]]: A dictionary containing the 'message' key which includes 'subject' (if applicable)
        and 'text' as keys representing the subject and body of the follow-up message respectively.

    Raises:
        ValueError: If an unknown channel is specified.
    """

    tasks = [
        checkEducation(reference),
        name_normalizer(receiver_name),
        generate_summary(profileData["_source"], True, reference),
        getSenderName(reference),
    ]

    if reference:
        tasks.extend(
            [personalisation_checker(reference), information_extractor(reference)]
        )

    else:
        tasks.extend(
            [personalisation_checker(texts[0]), information_extractor(texts[0])]
        )

    education = profileData["_source"].get("education", "")

    (
        isEducation,
        receiver_name,
        profileData,
        senderName,
        isPersonalised,
        (companies, links, contact),
    ) = await asyncio.gather(*tasks)

    isEducation = isEducation["flag"]

    if isEducation:
        profileEducation = ""
        if education:
            profileEducation = f"\nTotal Education history of {receiver_name}:\n"
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
        profileData += profileEducation

    senderName = senderName["sender_name"]
    senderName = senderName.strip()
    senderName = senderName.strip("'")
    senderName = senderName.strip('"')

    if "[" in senderName and "]" in senderName:
        senderName = ""
    if senderName:
        sender_name = senderName

    character_length = 0

    if channel == "email":
        if isPersonalised:
            system_prompt = deepcopy(FOLLOW_UP_EMAIL_PERSONALISED_SYSTEM_PROMPT)
            user_prompt = deepcopy(FOLLOW_UP_EMAIL_PERSONALISED_USER_PROMPT)
        else:
            system_prompt = deepcopy(FOLLOW_UP_EMAIL_SYSTEM_PROMPT)
            user_prompt = deepcopy(FOLLOW_UP_EMAIL_USER_PROMPT)

    elif channel == "linkedin_connect" or channel == "linkedin_premium":
        character_length = 160 if channel == "linkedin_connect" else 260

        if isPersonalised:
            system_prompt = deepcopy(FOLLOW_UP_LICONNECT_PERSONALISED_SYSTEM_PROMPT)
            user_prompt = deepcopy(FOLLOW_UP_LICONNECT_PERSONALISED_USER_PROMPT)
        else:
            system_prompt = deepcopy(FOLLOW_UP_LICONNECT_SYSTEM_PROMPT)
            user_prompt = deepcopy(FOLLOW_UP_LICONNECT_USER_PROMPT)

    elif channel == "linkedin_message":
        if isPersonalised:
            system_prompt = deepcopy(FOLLOW_UP_LI_PERSONALISED_SYSTEM_PROMPT)
            user_prompt = deepcopy(FOLLOW_UP_LI_PERSONALISED_USER_PROMPT)
        else:
            system_prompt = deepcopy(FOLLOW_UP_LI_SYSTEM_PROMPT)
            user_prompt = deepcopy(FOLLOW_UP_LI_USER_PROMPT)

    if len(texts) == 1:
        text = "Message Number 1:\n" + texts[0]
    else:
        text = ""
        for i in range(len(texts) - 1):
            text += f"Message Number {i+1}:\n" + texts[i] + "\n"
        text += f"Message Number {len(text)}:\n" + texts[-1]

    if character_length == 0:
        user_prompt = user_prompt.format(
            text=text,
            receiver_name=receiver_name,
            sender_name=sender_name,
            user_profile=profileData,
        )
    else:
        user_prompt = user_prompt.format(
            text=text,
            receiver_name=receiver_name,
            sender_name=sender_name,
            character_length=character_length,
            user_profile=profileData,
        )

    if links:
        user_prompt += f"Make sure you include these link without any alteration in your answer as done in reference: {links}"
    if companies:
        user_prompt += f"Ensure to add the names of the companies: {companies} as done in reference text"
    if contact:
        user_prompt += f"Make sure you include the contact details mentioned by the sender in reference text: {contact}"
    if isEducation:
        user_prompt += f"\nMake sure to mention educational experience of receiver"

    user_prompt += "\nIt is important that you follow the same writing style as reference to mimic sender's identity. For example writing the signing off the same way as done in reference."

    chat = [
        {
            "role": "system",
            "content": system_prompt
            + "\nJust return the message content and no extra explanation before or after message. Always make sure to generate a new followup message and never return the exact same content of the previous messages.",
        },
        {
            "role": "user",
            "content": user_prompt
            + "\nGenerate full links and urls as text and not hrefs",
        },
    ]
    response = await gpt_runner(model="gpt-4.1", temperature=0.2, chat=chat)

    if (channel == "linkedin_connect" or channel == "linkedin_premium") and len(
        response
    ) > character_length + 30:
        loop_count = 0
        while len(response) > character_length + 30:
            if loop_count >= 6:
                break
            response, chat_ = await gpt_reduce_length(
                response, character_length, loop_count
            )
            response = response.replace('"', "")
            loop_count += 1
        response = response.replace('"', "")
        follow_up_text = response
        return {"message": {"subject": None, "text": follow_up_text}}

    if (
        channel == "linkedin_connect"
        or channel == "linkedin_message"
        or channel == "linkedin_premium"
    ):
        response = response.replace('"', "")
        return {"message": {"subject": None, "text": response}}

    # print("Tokens:", response)
    response = response.split("\n")
    subject = response[0]
    subject = subject.replace("Subject:", "")
    # subject = subject.replace("Re:", "")
    subject = subject.replace("**", "").strip()
    # subject = subject.replace("Follow-Up:","").strip()

    response = "\n".join(response[1:])
    result = {"message": {"subject": subject, "text": response}}
    return result


async def generate_sample_pitch(
    reference: str,
    category: str,
    profileData_Original: Dict[str, Any],
    channel: str,
    sender_name: str,
    subject: str,
) -> Dict[str, Any]:
    position = ""
    profileData = profileData_Original["_source"]

    actual_reference = reference

    if profileData["fullName"] == "":
        profileName = profileData["firstName"] + " " + profileData["lastName"]
    else:
        profileName = profileData["fullName"]

    tasks = [
        name_normalizer(profileName),
        generate_summary(profileData, True, reference),
        personalisation_checker(actual_reference),
        getSenderName(actual_reference),
    ]

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

        (
            profileName,
            profile_summary,
            isPersonalised,
            senderName,
            res,
        ) = await asyncio.gather(*tasks)

        res = json.loads(res)
        if res["position"]:
            position += "\n".join(res["position"])

    else:
        (
            profileName,
            profile_summary,
            isPersonalised,
            senderName,
        ) = await asyncio.gather(*tasks)

    senderName = senderName["sender_name"]
    senderName = senderName.strip()
    senderName = senderName.strip("'")
    senderName = senderName.strip('"')

    if "[" in senderName and "]" in senderName:
        senderName = ""
    if senderName:
        sender_name = senderName

    system_prompt = deepcopy(PITCH_SAMPLE)
    user_prompt = ""

    if isPersonalised:
        if "none" not in profile_summary.lower():
            user_prompt = f"""<task> Given the reference message and the receiver's data, generate a call pitch for {category} domain</task>
        <reference_outreach_text> {reference} </reference_outreach_text>
        <receiver_info> {profile_summary} </receiver_info>
        <sender_name> {sender_name} </sender_name>"""
    if not user_prompt:
        user_prompt = f"""<task> Given the reference message and the receiver's data, generate a call pitch for {category} domain</task>
    <reference_outreach_text> {reference} </reference_outreach_text>
    <receiver_name> {profileName} </receiver_name>
    <sender_name> {sender_name} </sender_name>"""

    user_prompt += "\nMake sure that the message you generate is not exactly same as the reference.\n"
    if position:
        user_prompt += f"Position(s) referred in reference text: {position}"

    chat = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # print(chat)

    pitch = await gpt_runner(model="gpt-4.1", temperature=0.3, chat=chat)

    pitch = extract_generic("<pitch>", "</pitch>", pitch)
    pitch = pitch.replace('"', "")

    return {"message": {"subject": None, "text": pitch}}


async def generate_sample_followup_pitch(
    texts: List[str],
    channel: str,
    sender_name: str,
    receiver_name: str,
    reference: str,
    profileData: dict,
) -> Dict[str, Union[None, Dict[str, str]]]:

    tasks = [
        name_normalizer(receiver_name),
        generate_summary(profileData["_source"], True, reference),
        getSenderName(reference),
    ]

    if reference:
        tasks.extend([personalisation_checker(reference)])

    else:
        tasks.extend([personalisation_checker(texts[0])])

    (
        receiver_name,
        profileData,
        senderName,
        isPersonalised,
    ) = await asyncio.gather(*tasks)

    senderName = senderName["sender_name"]
    senderName = senderName.strip()
    senderName = senderName.strip("'")
    senderName = senderName.strip('"')

    if "[" in senderName and "]" in senderName:
        senderName = ""
    if senderName:
        sender_name = senderName

    user_prompt = ""

    if isPersonalised:
        if "none" not in profileData.lower():
            system_prompt = deepcopy(PITCH_SAMPLE_FOLLOWUP)
            user_prompt = f"""<task> Given the reference message and the receiver's data generate a call pitch </task>
            <reference_outreach_text> {reference} </reference_outreach_text>
            <receiver_info> {profileData} </receiver_info>
            <sender_name> {sender_name} </sender_name>"""
    if not user_prompt:
        system_prompt = deepcopy(PITCH_SAMPLE_FOLLOWUP)
        user_prompt = f"""<task> Given the reference message and the receiver's data, generate a call pitch </task>
        <reference_outreach_text> {reference} </reference_outreach_text>
        <receiver_info> {receiver_name} </receiver_info>
        <sender_name> {sender_name} </sender_name>"""

    if len(texts) == 1:
        text = "Call Number 1:\n" + texts[0]
    else:
        text = ""
        for i in range(len(texts) - 1):
            text += f"Call Number {i+1}:\n" + texts[i] + "\n"
        text += f"Call Number {len(text)}:\n" + texts[-1]

    chat = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]
    response = await gpt_runner(model="gpt-4.1", temperature=0.3, chat=chat)

    response = extract_generic("<followup_pitch>", "</followup_pitch>", response)

    result = {"message": {"subject": None, "text": response}}
    return result
