import os
from typing import Dict
from copy import deepcopy
from app.utils.outreach.services.generate_metrics.get_metrics_prompts import (
    METRICS_SYSTEM_PROMPT,
    METRICS_USER_PROMPT,
)
from app.utils.outreach.utils.gpt_utils.gpt_runner import gpt_runner

# GPT_MAIN_MODEL = os.getenv("GPT_MAIN_MODEL")
# GPT_COST_EFFICIENT_MODEL = os.getenv("GPT_COST_EFFICIENT_MODEL")
GPT_MAIN_MODEL = "gpt-4.1"
GPT_COST_EFFICIENT_MODEL = "gpt-4o-mini"


async def getMetrics(category: str) -> Dict:
    """
    Async Function to provide metrics for the specific label.

    Args:
    - category (str): Category for which metrics are to be generated

    Returns:
    - Metrics (Dictionary): Metric names along with their descriptions
    """
    systemPrompt = deepcopy(METRICS_SYSTEM_PROMPT)
    userPrompt = deepcopy(METRICS_USER_PROMPT)
    userPrompt = userPrompt.format(category=category)
    chat = [
        {"role": "system", "content": systemPrompt},
        {"role": "user", "content": userPrompt},
    ]
    response = await gpt_runner(
        chat, temperature=0.1, model="gpt-4.1", json_format=True
    )
    return response
