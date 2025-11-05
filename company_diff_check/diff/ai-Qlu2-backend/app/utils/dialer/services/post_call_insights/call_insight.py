import json
from copy import deepcopy
from app.utils.dialer.services.post_call_insights.call_insights_prompts import (
    CALLEE_INTEREST_DETECTION_SYSTEM_PROMPT,
    CALLEE_INTEREST_DETECTION_USER_PROMPT,
    CALLEE_FOLLOWUP_DETECTION_SYSTEM_PROMPT,
    CALLEE_FOLLOWUP_DETECTION_USER_PROMPT,
    CALLER_PITCH_USED_SYSTEM_PROMPT,
    CALLER_PITCH_DETECTION_USER_PROMPT,
)

from qutils.llm.asynchronous import invoke
from app.utils.dialer.utils.gpt_utils.gpt_models import (
    GPT_COST_EFFICIENT_MODEL,
    GPT_MAIN_MODEL,
)


async def get_callee_interest(transcriptions_data: list) -> str:

    sys_prompt = deepcopy(CALLEE_INTEREST_DETECTION_SYSTEM_PROMPT)

    # user_prompt = f"Here is the transcription of a live call. Analyze it and determine if the callee was interested or not.\n\n{transcriptions_data}"
    conversation = await format_conversation(transcriptions_data)
    user_prompt = CALLEE_INTEREST_DETECTION_USER_PROMPT.format(
        conversation_text=conversation
    )
    chat = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        response = await invoke(
            messages=chat,
            temperature=0.1,
            model=GPT_COST_EFFICIENT_MODEL,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        print(e)
        response = await invoke(
            messages=chat,
            temperature=0.1,
            model=GPT_MAIN_MODEL,
            response_format={"type": "json_object"},
        )
    response = json.loads(response)
    # print(f"reason of interest: {response['reason']}")
    return response["interested"]


async def get_callee_follow_up(transcriptions_data: list) -> str:

    sys_prompt = deepcopy(CALLEE_FOLLOWUP_DETECTION_SYSTEM_PROMPT)
    # user_prompt = f"Here is the transcription of a live call. Analyze it and determine if the callee was interested or not.\n\n{transcriptions_data}"
    conversation = await format_conversation(transcriptions_data)
    user_prompt = CALLEE_FOLLOWUP_DETECTION_USER_PROMPT.format(
        conversation_text=conversation
    )
    chat = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        response = await invoke(
            messages=chat,
            temperature=0.1,
            model=GPT_COST_EFFICIENT_MODEL,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        print(e)
        response = await invoke(
            messages=chat,
            temperature=0.1,
            model=GPT_MAIN_MODEL,
            response_format={"type": "json_object"},
        )
    response = json.loads(response)
    return response["follow_up"]


async def get_pitch_usage(transcriptions_data: list, pitch: str) -> str:
    sys_prompt = deepcopy(CALLER_PITCH_USED_SYSTEM_PROMPT)
    caller_transcriptions = await filter_caller_transcriptions(transcriptions_data)
    usr_prompt = CALLER_PITCH_DETECTION_USER_PROMPT.format(
        caller_transcriptions=caller_transcriptions, pitch_text=pitch
    )
    chat = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": usr_prompt},
    ]
    try:
        response = await invoke(
            messages=chat,
            temperature=0.1,
            model=GPT_COST_EFFICIENT_MODEL,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        print(e)
        response = await invoke(
            messages=chat,
            temperature=0.1,
            model=GPT_MAIN_MODEL,
            response_format={"type": "json_object"},
        )
    response = json.loads(response)
    # print(f"reason of pitch: {response['reason']}")
    return response["pitch_used"]


# Helper functions
async def format_conversation(transcriptions):
    """
    Converts a list of transcription dictionaries into a formatted conversation string.

    Args:
        transcriptions (list): List of dictionaries with 'track' (inbound/outbound) and 'text'.

    Returns:
        str: Formatted conversation text.
    """

    if not transcriptions or not isinstance(transcriptions, list):
        return ""

    formatted_lines = []

    for entry in transcriptions:
        if not isinstance(entry, dict):
            continue  # Skip invalid entries

        track = entry.get("track")
        text = entry.get("text")

        if (
            not track
            or not text
            or not isinstance(track, str)
            or not isinstance(text, str)
        ):
            continue  # Skip entries with missing or invalid data

        # Determine speaker
        if track == "inbound":
            speaker = "Caller"
        elif track == "outbound":
            speaker = "Callee"
        else:
            continue  # Ignore unknown track values

        formatted_lines.append(
            f"{speaker}: {text.strip()}"
        )  # Remove unnecessary spaces

    return "\n".join(formatted_lines)


async def filter_caller_transcriptions(transcriptions):
    """
    Filters and returns only the transcriptions of the caller.

    Args:
        transcriptions (list): List of dictionaries with 'speaker' and 'text'.

    Returns:
        list: List of caller's transcriptions.
    """
    if not transcriptions or not isinstance(transcriptions, list):
        return []

    return "\n".join(
        entry["text"] for entry in transcriptions if entry.get("track") == "inbound"
    )
