import json
from typing import Dict
from copy import deepcopy
from app.utils.dialer.services.generate_scores.get_scores_prompts import (
    SCORING_PROMPT_CONTINUE,
    SCORING_SYSTEM_PROMPT,
    SCORING_USER_PROMPT,
)

from qutils.llm.asynchronous import invoke
from app.utils.dialer.utils.gpt_utils.gpt_models import (
    GPT_COST_EFFICIENT_MODEL,
    GPT_MAIN_MODEL,
)

SCORES_THRESHOLD = {
    "Call to Action": 10,
    "Personalization": 15,
    "Common Ground": 10,
    "Incentives": 10,
    "Build Credibility": 15,
    "Flattery": 10,
}


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

    json_response = json.loads(response)
    scores = json_response["scores"]
    reasons = json_response["reasons"]

    # Convert scores less than 1 to percentage
    for key in scores:
        if scores[key] < 1:
            scores[key] = scores[key] * 100

    # --------------------- Currently Commenting as of not needed for now ---------------------
    # Check which metrics are below threshold and generate tooltips
    # below_threshold_metrics = []
    # for metric, score in scores.items():
    #     if metric in SCORES_THRESHOLD and score < SCORES_THRESHOLD[metric]:
    #         below_threshold_metrics.append(metric)

    # print(f"Printing below_threshold_metrics : \n{below_threshold_metrics}")
    # if below_threshold_metrics:
    #     tooltips = await generate_tooltips(
    #         category=category,
    #         metric_list=below_threshold_metrics,
    #         reasons_json={"reasons": reasons, "scores": scores},
    #         user_text=text
    #     )
    #     print(f"Printing tooltips : \n{tooltips}")
    # return {"scores": scores, "tooltips": tooltips}
    # --------------------- Currently Commenting as of not needed for now ---------------------

    return {"scores": scores}
