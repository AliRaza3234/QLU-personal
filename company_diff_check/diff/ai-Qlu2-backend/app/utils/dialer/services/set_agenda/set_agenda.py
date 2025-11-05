from copy import deepcopy

from app.utils.dialer.utils.gpt_utils.gpt_runner import gpt_runner
from app.utils.dialer.services.set_agenda.set_agenda_gv import (
    AGENDA_COLD_CALLING_PROMPT,
    AGENDA_PLANNER_PROMPT,
    AGENDA_INTENT_SYS_PROMPT,
    AGENDA_INTENT_USER_PROMPT,
    AGENDA_COLD_CALLING_SYSTEM_PROMPT,
    AGENDA_SETTER_PROMPT,
    AGENDA_SETTER_USER_PROMPT,
)

# Set Agenda (Start)
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def direct_agenda_planner(keys, intent):
    # system_prompt = deepcopy(AGENDA_PLANNER_PROMPT)
    if intent == "cold call":
        system_prompt = deepcopy(AGENDA_COLD_CALLING_PROMPT)
    else:
        system_prompt = deepcopy(AGENDA_PLANNER_PROMPT)
    chat = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": ", ".join(keys)},
    ]

    response = await gpt_runner(
        chat=chat, model="gpt-4o-mini", temperature=0, json_format=True
    )
    return response


async def agenda_intent(text):
    # print("text: ", text)
    system_prompt = deepcopy(AGENDA_INTENT_SYS_PROMPT)
    user_prompt = deepcopy(AGENDA_INTENT_USER_PROMPT)
    user_prompt = user_prompt.format(text)
    chat = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = await gpt_runner(
        chat=chat, model="gpt-4o", temperature=1, json_format=True
    )
    answer = response.get("intent", "")
    logger.info(f"Intent: {answer}")
    return answer


async def agenda_formatting(text):
    intent = await agenda_intent(text)
    if intent == "cold call":
        system_prompt = deepcopy(AGENDA_COLD_CALLING_SYSTEM_PROMPT)
    else:
        system_prompt = deepcopy(AGENDA_SETTER_PROMPT)

    user_prompt = deepcopy(AGENDA_SETTER_USER_PROMPT)
    user_prompt = user_prompt.format(text)
    user_prompt += """Example output format:"""
    user_prompt += "{"
    user_prompt += """  
"A": ["part1","part2"....],
"B": ["part1","part2"....],
    ...
}"""
    chat = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    response = await gpt_runner(
        chat=chat, model="gpt-4-0125-preview", temperature=0.1, json_format=True
    )

    if "error" in response:
        return {}
    plan = await direct_agenda_planner(list(response.keys()), intent)
    if "error" in plan:
        return {}

    last_response = {}
    for key, value in response.items():
        if key in plan:
            if intent == "cold call":
                last_response[key] = {
                    "time": round(int(plan[key]) / 60, 2),
                    "parts": value,
                }
            else:
                last_response[key] = {"time": plan[key], "parts": value}
        else:
            last_response[key] = {"time": "N/A", "parts": value}

    return {"data": last_response, "intent": intent}


# Set Agenda (End)
