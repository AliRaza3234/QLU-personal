import os
from copy import deepcopy
from app.utils.dialer.utils.gpt_utils.gpt_runner import gpt_runner
from app.utils.dialer.services.generate_category.get_category_prompts import (
    ROUTER_AGENT_TEXT_SYSTEM_PROMPT,
    ROUTER_AGENT_TEXT_USER_PROMPT,
)

from app.utils.dialer.utils.gpt_utils.gpt_models import (
    GPT_COST_EFFICIENT_MODEL,
    GPT_MAIN_MODEL,
)


async def getCategory(text: str) -> str:
    """
    Async Function to provide label to message.

    Args:
    - text (str): Message that needs to be assigned a label

    Returns:
    - label (str): The generated label
    """
    systemPrompt = deepcopy(ROUTER_AGENT_TEXT_SYSTEM_PROMPT)
    userPrompt = deepcopy(ROUTER_AGENT_TEXT_USER_PROMPT)
    userPrompt = userPrompt.format(text=text)
    chat = [
        {"role": "system", "content": systemPrompt},
        {"role": "user", "content": userPrompt},
    ]
    response = ""
    try:
        response = await gpt_runner(
            chat=chat, temperature=0.1, model=GPT_COST_EFFICIENT_MODEL
        )
    except Exception as e:
        print(e)
        response = await gpt_runner(chat=chat, temperature=0.1, model=GPT_MAIN_MODEL)
    return response
