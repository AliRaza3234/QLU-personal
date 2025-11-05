import os
from typing import Dict
from copy import deepcopy
from app.utils.dialer.services.generate_metrics.get_metrics_prompts import (
    METRICS_SYSTEM_PROMPT,
    METRICS_USER_PROMPT,
)
from app.utils.dialer.utils.gpt_utils.gpt_runner import gpt_runner

from app.utils.dialer.utils.gpt_utils.gpt_models import GPT_MAIN_MODEL, GPT_BACKUP_MODEL


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
    try:
        response = await gpt_runner(chat=chat, temperature=0.1, model=GPT_MAIN_MODEL)
    except Exception as e:
        print(e)
        response = await gpt_runner(chat=chat, temperature=0.1, model=GPT_BACKUP_MODEL)
    return response
