import json
from copy import deepcopy
from app.utils.dialer.services.callee_interest.callee_interest_prompts import (
    CALLER_INTEREST_DETECTION_SYSTEM_PROMPT,
    CALLER_INTEREST_DETECTION_USER_PROMPT,
)

from app.utils.dialer.utils.gpt_utils.gpt_models import (
    GPT_COST_EFFICIENT_MODEL,
    GPT_MAIN_MODEL,
)
from qutils.llm.asynchronous import invoke


async def generate_callee_interest(callee_data: str, caller_data: str) -> str:

    sys_prompt = deepcopy(CALLER_INTEREST_DETECTION_SYSTEM_PROMPT)
    user_prompt = deepcopy(CALLER_INTEREST_DETECTION_USER_PROMPT)

    user_prompt = user_prompt.format(caller_data=caller_data, callee_data=callee_data)

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
    return response["interest"]
