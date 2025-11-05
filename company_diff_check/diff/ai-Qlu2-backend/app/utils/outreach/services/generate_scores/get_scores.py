import json
from typing import Dict
from copy import deepcopy
from app.utils.outreach.services.generate_scores.get_scores_prompts import (
    SCORING_PROMPT_CONTINUE,
    SCORING_SYSTEM_PROMPT,
    SCORING_USER_PROMPT,
)
from app.utils.outreach.utils.gpt_utils.gpt_runner import gpt_runner

# GPT_MAIN_MODEL = os.getenv("GPT_MAIN_MODEL")
GPT_MAIN_MODEL = "gpt-4.1"


async def getScores(text: str, attributes: Dict, category: str) -> Dict:
    """
    Async Function to provide scores for a piece of text of a specific category against some metrics.

    Args:
    - text (str): Message that is to be assigned a score
    - attributes (dict): The metrics against which scores are to be generated
    - category (str): The intent of thr messsage

    Returns:
    - Scores (dict): The scores against each metric
    """
    systemPrompt = deepcopy(SCORING_SYSTEM_PROMPT)
    userPrompt = deepcopy(SCORING_USER_PROMPT)
    # print(f"Printing attributes = {attributes}")
    # print(type(attributes))
    systemPrompt = systemPrompt.format(attributes=attributes)
    systemPrompt += deepcopy(SCORING_PROMPT_CONTINUE)
    userPrompt = userPrompt.format(
        text=text,
        category=category,
    )
    chat = [
        {"role": "system", "content": systemPrompt},
        {"role": "user", "content": userPrompt},
    ]
    response = await gpt_runner(
        chat, temperature=0.1, model=GPT_MAIN_MODEL, json_format=True
    )
    scores = json.loads(response)
    for key in scores:
        if scores[key] < 1:
            scores[key] = scores[key] * 100
    return scores
