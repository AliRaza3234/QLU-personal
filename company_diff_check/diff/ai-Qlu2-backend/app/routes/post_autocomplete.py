import re
import json
import traceback
from fastapi import APIRouter, HTTPException
from app.utils.search.qsearch.autocomplete.prompts import prompt_template
from app.models.schemas.autocomplete import AutoCompleteInput, AutoCompleteOutput
from qutils.llm.asynchronous import invoke
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


def remove_words_with_multiple_spaces(strings):
    updated_strings = []
    for string in strings:
        if string.count(" ") <= 1:
            updated_strings.append(string)
    return updated_strings


def extract_json_from_response(response):
    json_pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
    match = re.search(json_pattern, response, re.DOTALL)
    if match:
        return match.group(1)
    json_obj_pattern = r'(\{[^{}]*"keywords"[^{}]*\})'
    match = re.search(json_obj_pattern, response, re.DOTALL)
    if match:
        return match.group(1)
    return response


def parse_degrees_response(response):
    entity_list = set()

    try:
        json_str = extract_json_from_response(response)
        response_data = json.loads(json_str)
        if "keywords" in response_data and isinstance(response_data["keywords"], list):
            for keyword in response_data["keywords"]:
                if isinstance(keyword, str):
                    cleaned = keyword.strip().strip('"').strip(",").strip()
                    if cleaned and not cleaned.lower().startswith("sorry"):
                        entity_list.add(cleaned)

    except (json.JSONDecodeError, ValueError) as e:
        degree_pattern = r'"?([A-Z][^",\n{}[\]]+(?:\s*-\s*[A-Z]+)?)"?'
        matches = re.findall(degree_pattern, response)
        for match in matches:
            cleaned = match.strip().strip('"').strip(",").strip()
            if (
                cleaned
                and not cleaned in ["keywords", "{", "}", "[", "]", "```json", "```"]
                and not cleaned.lower().startswith("sorry")
                and len(cleaned) > 2
            ):
                entity_list.add(cleaned)
    return list(entity_list)


@router.post(f"/autocomplete", response_model=AutoCompleteOutput)
async def autocomplete(request: AutoCompleteInput) -> list[str]:
    try:
        entity = re.sub(r"[^A-Za-z0-9\s]", "", request.uncomplete_entity)
        output = AutoCompleteOutput(entity_list=[])

        if request.entity_type == "degrees":
            model = "openai/gpt-4.1-mini"
        else:
            model = "openai/gpt-4o-mini"

        if not all(char == "" for char in entity):
            messages = prompt_template(request.entity_type, entity)
            response = await invoke(
                messages=messages,
                model=model,
                fallbacks=["anthropic/claude-3-5-haiku-latest"],
                temperature=0.3,
            )

            entity_list = set()

            if request.entity_type == "degrees":
                entity_list = parse_degrees_response(response)
            else:
                response_lines = response.split("\n")

                for line in response_lines:
                    word_list = line.split(" ")
                    if len(word_list) > 8 or "sorry" in line:
                        continue
                    current_entity = " ".join(word_list[1:])
                    current_entity = current_entity.split("(", maxsplit=1)[0].strip()
                    if len(current_entity) > 0:
                        entity_list.add(current_entity)

            if request.entity_type == "skills" or request.entity_type == "industries":
                entity_list = remove_words_with_multiple_spaces(list(entity_list))
            else:
                entity_list = list(entity_list)
            output = AutoCompleteOutput(entity_list=entity_list)
        return output

    except Exception as e:
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="autocomplete",
            service_name="AUTOCOMPLETE",
        )
        raise HTTPException(
            status_code=500, detail={"error": str(e), "traceback": error_trace}
        )
