import os
from copy import deepcopy
from app.utils.outreach.utils.gpt_utils.gpt_runner import gpt_runner
from app.utils.outreach.services.generate_category.get_category_prompts import (
    ROUTER_AGENT_TEXT_SYSTEM_PROMPT,
    ROUTER_AGENT_TEXT_USER_PROMPT,
)

# GPT_MAIN_MODEL = os.getenv("GPT_MAIN_MODEL")
# GPT_COST_EFFICIENT_MODEL = os.getenv("GPT_COST_EFFICIENT_MODEL")
GPT_MAIN_MODEL = "gpt-4.1"
GPT_COST_EFFICIENT_MODEL = "gpt-4o-mini"


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
    response = await gpt_runner(
        chat, temperature=0.1, model="gpt-4.1", json_format=True
    )
    return response
