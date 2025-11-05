import json
from copy import deepcopy

from app.utils.dialer.services.call_summary.call_summ_gv import (
    RECRUITEMENT_SUMMARY_SYS_PROMPT,
    RECRUITEMENT_SUMMARY_USER_PROMPT,
    COLD_CALL_SUMMARY_SYSTEM_PROMPT,
    COLD_CALL_SUMMARY_USER_PROMPT,
    SUMMARY_PAYLOAD,
)

from app.utils.dialer.utils.gpt_utils.gpt_models import (
    GPT_COST_EFFICIENT_MODEL,
    GPT_MAIN_MODEL,
)

from qutils.llm.asynchronous import invoke
from app.utils.dialer.utils.gpt_utils.gpt_utils import subject_generator


async def generate_summary_cold_call(transcriptions: str) -> str:

    summary_sys_prompt = deepcopy(COLD_CALL_SUMMARY_SYSTEM_PROMPT)
    summary_user_prompt = deepcopy(COLD_CALL_SUMMARY_USER_PROMPT)
    summary_payload = deepcopy(SUMMARY_PAYLOAD)

    summary_user_prompt = summary_user_prompt.format(transcriptions)
    summary_chat = [
        {"role": "system", "content": summary_sys_prompt},
        {"role": "user", "content": summary_user_prompt},
    ]

    try:
        summary_response = await invoke(
            messages=summary_chat,
            temperature=0.1,
            model=GPT_MAIN_MODEL,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        print("Exception: ", e)
        summary_response = await invoke(
            messages=summary_chat,
            temperature=0.1,
            model=GPT_MAIN_MODEL,
            response_format={"type": "json_object"},
        )
    summary_response = json.loads(summary_response)

    summary = summary_response.get("summary", "[[sorry]]")
    if "[[sorry]]" == summary:
        return ""

    summary_response["summary"] = summary_response["summary"].replace("- ", "")

    subject_response = await subject_generator(summary_response["summary"])

    summary_payload["summary"] = summary_response.get("summary")
    summary_payload["tone"] = summary_response.get("tone")

    summary_payload["subject"] = subject_response
    return summary_payload


async def generate_summary_recuritement(transcriptions: str) -> str:
    summary_sys_prompt = deepcopy(RECRUITEMENT_SUMMARY_SYS_PROMPT)
    summary_user_prompt = deepcopy(RECRUITEMENT_SUMMARY_USER_PROMPT)
    summary_payload = deepcopy(SUMMARY_PAYLOAD)

    summary_user_prompt = summary_user_prompt.format(transcriptions)
    summary_chat = [
        {"role": "system", "content": summary_sys_prompt},
        {"role": "user", "content": summary_user_prompt},
    ]
    try:
        summary_response = await invoke(
            messages=summary_chat,
            temperature=0.1,
            model=GPT_COST_EFFICIENT_MODEL,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        print(e)
        summary_response = await invoke(
            messages=summary_chat,
            temperature=0.1,
            model=GPT_MAIN_MODEL,
            response_format={"type": "json_object"},
        )

    summary_response = json.loads(summary_response)  # Ensure it's a valid JSON string

    # Extract summary and tone
    summary_data = summary_response.get("summary", "")
    summary_tone = summary_response.get("tone", "")

    # Clean up the summary
    summary_data = summary_data.replace("- ", "")

    # Check for a specific response
    if "[[sorry]]" == summary_data:
        return summary_payload

    # Generate the subject response
    subject_response = await subject_generator(summary_data)

    # Updating the payload
    summary_payload["summary"] = summary_data
    summary_payload["tone"] = summary_tone
    summary_payload["subject"] = subject_response

    return summary_payload
