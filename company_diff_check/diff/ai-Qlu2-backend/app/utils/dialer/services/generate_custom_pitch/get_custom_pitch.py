import json
from copy import deepcopy

from qutils.llm.asynchronous import invoke
from app.utils.dialer.services.generate_custom_pitch.get_custom_pitch_prompts import (
    CUSTOM_PITCH_SYSTEM_PROMPT,
    CUSTOM_PITCH_USER_PROMPT,
)

from app.utils.dialer.utils.gpt_utils.gpt_models import GPT_MAIN_MODEL, GPT_BACKUP_MODEL


async def get_custom_pitch_converter(reference_text: str, callee_name: str) -> str:
    reference_text = reference_text.strip()
    if reference_text == "":
        return {"pitch": ""}

    system_prompt = deepcopy(CUSTOM_PITCH_SYSTEM_PROMPT)
    user_prompt = deepcopy(CUSTOM_PITCH_USER_PROMPT)

    user_prompt = user_prompt.format(
        reference_text=reference_text, callee_name=callee_name
    )
    chat = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        custom_pitch = await invoke(
            messages=chat,
            temperature=0.1,
            model=GPT_MAIN_MODEL,
            response_format={"type": "json_object"},
        )
        custom_pitch = json.loads(custom_pitch)
    except Exception as e:
        print(e)
        custom_pitch = await invoke(
            messages=chat,
            temperature=0.1,
            model=GPT_BACKUP_MODEL,
            response_format={"type": "json_object"},
        )
        custom_pitch = json.loads(custom_pitch)

    result = custom_pitch["text"].strip()
    if result == "":
        return {"pitch": reference_text}
    return {"pitch": result}
