import json
import re
from typing import List
from copy import deepcopy
from app.utils.search.qsearch.suggestions.prompts import (
    SUGGESTED_TERMS_SYSTEM_PROMPTS,
    SUGGESTED_TERMS_USER_PROMPTS,
    INDUSTRY_SUGGEST_SYSTEM_PROMPT,
    INDUSTRY_SUGGEST_USER_PROMPT,
)
from qutils.llm.asynchronous import invoke


async def suggest_terms(entity: str, entity_type: str) -> List[str]:
    if entity_type == "industries":
        systemPrompt = deepcopy(INDUSTRY_SUGGEST_SYSTEM_PROMPT)
        userPrompt = deepcopy(INDUSTRY_SUGGEST_USER_PROMPT)
    else:
        systemPrompt = deepcopy(SUGGESTED_TERMS_SYSTEM_PROMPTS)
        userPrompt = deepcopy(SUGGESTED_TERMS_USER_PROMPTS)
    userPrompt = userPrompt.format(entity=entity, entity_type=entity_type)

    if entity_type == "skills":
        userPrompt += "\nDon't generate any skill with more than 2 words."

    gpt_response_text = await invoke(
        messages=[
            {"role": "system", "content": systemPrompt},
            {"role": "user", "content": userPrompt},
        ],
        temperature=0.3,
        model="openai/gpt-4o-mini",
        fallbacks=["anthropic/claude-3-5-haiku-latest"],
    )

    try:
        gpt_response_dct = json.loads(gpt_response_text)
    except json.JSONDecodeError:
        start = gpt_response_text.find("{")
        end = gpt_response_text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                gpt_response_dct = json.loads(gpt_response_text[start : end + 1])
            except json.JSONDecodeError:
                gpt_response_dct = {}
        else:
            gpt_response_dct = {}

    if "keywords" in gpt_response_dct:
        suggestedLst = [i for i in gpt_response_dct["keywords"]]
        return suggestedLst if len(suggestedLst) > 4 else []

    suggestedLst = []
    if gpt_response_dct:
        gpt_response_dct = dict(
            sorted(gpt_response_dct.items(), key=lambda item: item[1], reverse=True)
        )
        for suggestion in gpt_response_dct:
            match = re.match(r"(.*)\((.*)\)", suggestion)
            if match:
                outside_text = match.group(1).strip()
                inside_text = match.group(2).strip()
                suggestedLst.append(outside_text)
                suggestedLst.append(inside_text)
            else:
                suggestedLst.append(suggestion)
            if len(suggestedLst) > 4:
                break
        suggestedLst = [i.replace("'", "") for i in suggestedLst]
        suggestedLst = [i.replace('"', "") for i in suggestedLst]
        suggestedLst = [i.replace("_", " ") for i in suggestedLst]
    return suggestedLst if len(suggestedLst) > 4 else []
