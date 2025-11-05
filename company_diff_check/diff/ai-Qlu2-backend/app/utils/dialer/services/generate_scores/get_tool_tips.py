import json
from app.utils.dialer.services.generate_scores.get_scores_prompts import (
    TOOLTIP_SYSTEM_PROPMT,
)
from copy import deepcopy
from qutils.llm.asynchronous import invoke
from app.utils.dialer.utils.gpt_utils.gpt_models import (
    GPT_MAIN_MODEL,
    GPT_COST_EFFICIENT_MODEL,
)


async def generate_tooltips(category, metric_list, reasons_json, user_text):
    metrics_formatted = "\n".join(f"- {metric}" for metric in metric_list)

    user_prompt = f"""
    <intent>
    {category}
    </intent>
    <metrics>
    {metrics_formatted}
    </metrics>
    <user_text>
    {user_text}
    </user_text>
    """

    final_prompt = TOOLTIP_SYSTEM_PROPMT + "\n" + user_prompt

    response = await invoke(
        messages=[
            {"role": "system", "content": final_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=GPT_COST_EFFICIENT_MODEL,
        temperature=0.1,
    )

    return response
