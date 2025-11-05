from copy import deepcopy
from app.utils.dialer.utils.gpt_utils.gpt_runner import gpt_runner, direct_gpt_runner
from app.utils.dialer.services.generate_threshold.gen_threshold_prompts import (
    THRESHOLD_SYSTEM_PROMPT,
    THRESHOLD_USER_PROMPT,
)
from app.utils.dialer.utils.gpt_utils.gpt_models import GPT_3_TURBO_MODEL


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
    try:
        response = await gpt_runner(chat=chat, temperature=0.1, model=GPT_3_TURBO_MODEL)
    except Exception as e:
        print(e, "Retrying ... ")

        response = await gpt_runner(chat=chat, temperature=0.1, model=GPT_3_TURBO_MODEL)
    return response


def directgetThresholds(label: str, metrics: dict) -> dict:
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
    try:
        response = direct_gpt_runner(
            chat=chat, temperature=0.1, model=GPT_3_TURBO_MODEL
        )
    except Exception as e:
        print(e, "Retrying ... ")

        response = direct_gpt_runner(
            chat=chat, temperature=0.1, model=GPT_3_TURBO_MODEL
        )
    return response


metrics = {
    "Call to Action": "Evaluate the clarity and effectiveness of the request for the recipient to take the next step, such as scheduling a meeting or demo.",
    "Personalization": "Assess how well the pitch is tailored to the recipient, reflecting their specific industry, role, or challenges.",
    "Common Ground": "Evaluate how effectively the pitch establishes a connection or shared interest with the recipient, building rapport early in the call.",
    "Incentive": "Examine if the pitch offers a clear incentive or benefit for the recipient, motivating them to engage further.",
    "Build Credibility": "Assess the presence of trust-building elements, such as data, case studies, or testimonials that support the claims made.",
    "Flattery": "Determine if the pitch uses genuine compliments or positive reinforcement to build rapport and make the recipient more receptive.",
}
import asyncio

result = directgetThresholds(label="sales pitch", metrics=metrics)
print(result)
