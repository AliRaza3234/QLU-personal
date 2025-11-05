import json
import contractions, re
from copy import deepcopy
from openai import AsyncOpenAI

from app.utils.dialer.services.agenda_checker.agenda_check_gv import (
    POST_AGENDA_SYS_PROMPT,
    POST_AGENDA_USER_PROMPT,
    POST_AGENDA_OUTPUT_PAYLOAD,
)

from app.utils.dialer.utils.clean_format.clean_format import (
    clean_and_combine_texts,
    text_indexed_converter,
)
from app.utils.dialer.utils.gpt_utils.gpt_utils import sentence_formatter
from app.utils.dialer.utils.gpt_utils.gpt_runner import gpt_runner


def agenda_input_parser(data: list) -> tuple:
    """
    Parses agenda data into a structured format.

    Args:
    - data (list): List of dictionaries with agenda sections and questions.

    Returns:
    - tuple:
      - agenda_ids (set): Set of agenda IDs.
      - agenda_string (str): Concatenated string of "ID: Question" pairs.
      - agenda_sections (dict): Dictionary of agenda sections with questions.
    """
    agendas = dict()
    agenda_sections = dict()
    for section in data:
        agenda_sections[str(section["title"])] = []
        for question in section["questions"]:
            agendas[str(question["id"])] = question["question"]
            agenda_sections[str(section["title"])].append(
                (str(question["id"]), question["question"])
            )
    agenda_string = ""
    agenda_ids = set()
    for title, agendas in agenda_sections.items():
        for agenda in agendas:
            agenda_string += f"{agenda[0]}: {agenda[1]}\n"
            agenda_ids.add(str(agenda[0]))

    return agenda_ids, agenda_string, agenda_sections


async def answer_detection_for_agenda(text_list: str, agenda: dict) -> dict:

    cleaned_transcription_list = await sentence_formatter(
        clean_and_combine_texts(text_list)
    )
    agenda_ids, agenda_string, agenda_sections = agenda_input_parser(agenda)

    transcription_indexed_text = text_indexed_converter(cleaned_transcription_list)

    sys_prompt = deepcopy(POST_AGENDA_SYS_PROMPT)
    user_prompt = deepcopy(POST_AGENDA_USER_PROMPT)
    output_payload = deepcopy(POST_AGENDA_OUTPUT_PAYLOAD)

    user_prompt = user_prompt.format(transcription_indexed_text, agenda_string)

    chat = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = await gpt_runner(
        chat=chat, model="gpt-4o-mini", temperature=0.2, json_format=False
    )

    return await make_all_output_payload(
        response, text_list, output_payload, agenda_ids, agenda_sections
    )


async def make_all_output_payload(
    response, outbound_data, post_output_payload, agenda_ids, agenda_sections
):
    results = response.split("\n")
    all_questions = {}
    for section, agendas in agenda_sections.items():
        for agenda in agendas:
            all_questions[str(agenda[0])] = agenda[1]

    all_payloads = {"agenda_marked": []}
    temp_payload = deepcopy(post_output_payload)
    for result in results:
        tokens = result.split("~")
        if (
            len(tokens) == 2
            and str(tokens[0]) in agenda_ids
            and "none" not in tokens[1].lower()
        ):
            id_, indexes = str(tokens[0]), eval(tokens[1])
            temp_payload = deepcopy(post_output_payload)

            temp_payload["question_id"] = id_
            temp_payload["question"] = all_questions[id_]
            answers = []
            start, end, answer = -1, -1, ""
            for idx, current in enumerate(indexes):
                start = start if start != -1 else current
                end = current
                answer += outbound_data[end] + " "
                if end == indexes[-1]:
                    answers.append({"start": start * 5, "end": end * 5, "text": answer})
                elif (idx + 1) < len(indexes) and indexes[idx + 1] != end + 1:
                    answers.append({"start": start * 5, "end": end * 5, "text": answer})
                    start, answer = -1, ""

            temp_payload["answers"] = deepcopy(answers)
        all_payloads["agenda_marked"].append(deepcopy(temp_payload))

    return all_payloads
