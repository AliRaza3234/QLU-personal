from copy import deepcopy
from app.utils.outreach.utils.gpt_utils.gpt_runner import gpt_runner
from app.utils.outreach.services.generate_threshold.gen_threshold_prompts import (
    THRESHOLD_SYSTEM_PROMPT,
    THRESHOLD_USER_PROMPT,
)

# GPT_MAIN_MODEL = os.getenv("GPT_MAIN_MODEL")
GPT_MAIN_MODEL = "gpt-4o"
# GPT_COST_EFFICIENT_MODEL = os.getenv("GPT_COST_EFFICIENT_MODEL")
GPT_COST_EFFICIENT_MODEL = "gpt-4o-mini"


async def getThresholds(label: str, metrics: dict) -> dict:
    """
    Async Function to provide score thresholds for a specific category against some metrics.

    Args:
    - label (str): The intent of the messsage
    - metrics (dict): The metrics against which score thresholds are to be generated

    Returns:
    - Score thresholds (dict): The score thresholds against each metric
    """
    systemPrompt = deepcopy(THRESHOLD_SYSTEM_PROMPT)
    userPrompt = deepcopy(THRESHOLD_USER_PROMPT)
    userPrompt = userPrompt.format(intent=label, metrics=metrics)

    chat = [
        {"role": "system", "content": systemPrompt},
        {"role": "user", "content": userPrompt},
    ]
    response = await gpt_runner(
        chat, temperature=0.1, model="gpt-4.1-mini", json_format=True
    )
    return response
