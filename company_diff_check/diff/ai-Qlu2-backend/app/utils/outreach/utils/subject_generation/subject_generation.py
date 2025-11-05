# import os
import json
from copy import deepcopy
from app.utils.outreach.utils.subject_generation.subject_generation_prompts import (
    SUBJECT_GENERATION_USER_PROMPT,
    SUBJECT_GENERATION_SYSTEM_PROMPT,
    SUBJECT_GENERATION_SAMPLE_SYSTEM_PROMPT,
    SUBJECT_GENERATION_SAMPLE_USER_PROMPT,
)
from app.utils.outreach.utils.gpt_utils.gpt_runner import gpt_runner
from app.utils.outreach.utils.gpt_utils.gpt_utils import extract_generic


async def subject_generation(
    email: str,
    reference_subject: str = "",
    sample=True,
    profile_summary="",
    sender_name="",
    is_subject_personalized=False,
) -> str:
    """
    Async function to generate a subject for email using the reference subject and the generated email

    Args:
    - email (str): Email for which subject is to be generated
    - reference_subject (str): Reference subject that is to be used while generating new subjects

    Returns:
    - str: Subject
    """
    model = None
    temperature = 0
    isReference = False
    no_call = False
    if sample:
        systemPrompt = deepcopy(SUBJECT_GENERATION_SAMPLE_SYSTEM_PROMPT)
        userPrompt = deepcopy(SUBJECT_GENERATION_SAMPLE_USER_PROMPT)
        model = "gpt-4.1"
        temperature = 0.3
    else:
        if reference_subject:
            isReference = True
            if not is_subject_personalized:
                no_call = True
                # systemPrompt = deepcopy(SUBJECT_GENERATION_SYSTEM_PROMPT)
                # userPrompt = deepcopy(SUBJECT_GENERATION_USER_PROMPT)
                # model = "gpt-4.1-mini"
                # temperature = 0.1
                # isReference = True
            else:
                systemPrompt = deepcopy(SUBJECT_GENERATION_SYSTEM_PROMPT)
                userPrompt = deepcopy(SUBJECT_GENERATION_USER_PROMPT)
                model = "gpt-4.1-mini"
                temperature = 0.2
        else:
            systemPrompt = deepcopy(SUBJECT_GENERATION_SAMPLE_SYSTEM_PROMPT)
            userPrompt = deepcopy(SUBJECT_GENERATION_SAMPLE_USER_PROMPT)
            model = "gpt-4.1"
            temperature = 0.3

    if no_call:
        outreach_text = reference_subject
    else:
        userPrompt = userPrompt.format(
            email=email,
            subject=reference_subject,
            profile_summary=profile_summary,
            sender_name=sender_name,
        )
        chat = [
            {"role": "system", "content": systemPrompt},
            {"role": "user", "content": userPrompt},
        ]
        outreach_text = await gpt_runner(
            model=model, temperature=temperature, chat=chat
        )

        if isReference:
            outreach_text = extract_generic(
                "<new_subject>", "</new_subject>", outreach_text
            )

    outreach_text = outreach_text.strip('"')
    outreach_text = outreach_text.strip("'")
    outreach_text = outreach_text.strip()

    return outreach_text
