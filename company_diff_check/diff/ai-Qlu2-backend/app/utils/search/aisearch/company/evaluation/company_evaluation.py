import json
import asyncio
import traceback
from app.utils.search.aisearch.company.evaluation.prompts import *
from app.utils.search.aisearch.company.evaluation.utils import (
    proxy_inference,
    extract_and_decode_url,
    verify_substring_index,
)

from qutils.llm.asynchronous import invoke


async def questions_extraction(company, prompt):
    user_prompt = (
        QUESTIONS_KEYPOINTS_USER_PROMPT
        + f"""
        <Company>
        Name: {company}
        </Company>

        <User Query>
        Query : {prompt}
        </User Query>
        """
    )
    response = await invoke(
        messages=[
            {"role": "system", "content": QUESTIONS_KEYPOINTS_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        model="groq/llama-3.3-70b-versatile",
        fallbacks=["openai/gpt-4.1"],
    )
    questions = response.split("<Questions>")[1].split("</Questions>")[0].strip()
    if "None" in questions or questions == "":
        return None, None, None
    keypoints = response.split("<Keypoints>")[1].split("</Keypoints>")[0].strip()
    seo = response.split("<SEO>")[1].split("</SEO>")[0].strip()
    questions_list = questions.split("~")
    keypoints_list = keypoints.split("~")
    seo_list = seo.split("~")
    return questions_list, keypoints_list, seo_list


async def verifying_companies(question, source, max_retries=3):
    for attempt in range(max_retries + 1):
        try:
            user_prompt = (
                CONTEXT_CHECKING_USER_PROMPT
                + f"""
                <Question>
                Query: {question}
                </Question>

                <Context>
                Websearch Results : {source}
                </Context>
                """
            )
            response = await invoke(
                messages=[
                    {"role": "system", "content": CONTEXT_CHECKING_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
                model="groq/llama-3.3-70b-versatile",
                fallbacks=["openai/gpt-4.1"],
            )
            verification = (
                response.split("<Response>")[1].split("</Response>")[0].strip()
            )
            verification = verification.split("|||")
            return verification
        except Exception:
            if attempt == max_retries:
                return []
            await asyncio.sleep(2**attempt)


async def correcting_reponse(user_query, company, points, information):
    user_prompt = (
        CORRECTION_USER_PROMPT
        + f"""
        <User Query>
        Query: {user_query}
        </User Query>

        <Company>
        Company name: {company}
        </Company>

        <Keypoints>
        Keypoints : {points}
        </Keypoints>

        <Additional Factual Information>
        Information : {information}
        </Additional Factual Information>
        """
    )
    response = await invoke(
        messages=[
            {"role": "system", "content": CORRECTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        model="openai/gpt-4.1",
        fallbacks=["anthropic/claude-sonnet-4-latest"],
    )
    statement = response.split("<Query>")[1].split("</Query>")[0].strip()
    keypoints = response.split("<Keypoints>")[1].split("</Keypoints>")[0].strip()
    keypoints_list = keypoints.split("~")
    return statement, keypoints_list


async def main(prompt, company):
    try:
        company_name = company["es_data"]["name"]
        questions, keypoints, seos = await questions_extraction(company_name, prompt)

        if questions == None or keypoints == None or seos == None:
            return json.dumps(
                {
                    "es_data": company["es_data"],
                    "response_string": "",
                    "ner": [],
                }
            )

        task_web_search = []
        for question in seos:
            task_web_search.append(proxy_inference(question))
        result_web_search = await asyncio.gather(*task_web_search)

        if None in result_web_search:
            response_data = {
                "es_data": company["es_data"],
                "response_string": "",
                "ner": [],
            }
            return json.dumps(response_data)

        result_web_search = [result["query_result"][:] for result in result_web_search]

        task_verify_search = []
        for ques, context in zip(questions, result_web_search):
            task_verify_search.append(verifying_companies(ques, context))
        result_verify_web_search = await asyncio.gather(*task_verify_search)

        verification = [item[0] for item in result_verify_web_search]
        sources = [item[1] for item in result_verify_web_search]
        additional_information = [
            item[2]
            for item in result_verify_web_search
            if len(item) > 2 and item[2] is not None
        ]

        corrected_information = await correcting_reponse(
            prompt, company_name, keypoints, additional_information
        )

        corrected_information_list = list(corrected_information)

        corrected_information_list[1] = [
            entry.replace("'", "") for entry in corrected_information_list[1]
        ]

        count = 0
        ner_output = []
        try:
            for ner, source, ver in zip(
                corrected_information[1], sources, verification
            ):
                if count > len(keypoints):
                    break
                else:
                    if source.startswith("https://r.search.yahoo.com"):
                        source = extract_and_decode_url(source)
                    data = ner.replace("'", "")
                    start = corrected_information[0].lower().find(ner.lower())
                    end = (
                        corrected_information[0].lower().find(ner.lower())
                        + len(ner)
                        - 1
                    )
                    if start == -1:
                        index = verify_substring_index(corrected_information[0], data)
                        if index is not None and len(index) == 2:
                            start = index[0]
                            end = index[1]
                            data = (
                                corrected_information[0][start:end]
                                if start > 0 and end > 0
                                else data
                            )
                    ner_output.append(
                        {
                            "data": data,
                            "start": start,
                            "end": end,
                            "sources": source if ver != "None" else None,
                            "verification": True if ver.lower() == "yes" else False,
                        }
                    )
                count += 1
        except Exception as e:
            print("Error when trying NER: ", {e})

        output = {"response_string": corrected_information[0], "ner": ner_output}

        seen = set()
        new_ner = []
        for entry in output["ner"]:
            entry_tuple = tuple(entry.items())
            if entry_tuple not in seen:
                seen.add(entry_tuple)
                new_ner.append(entry)

        final_output = {
            "es_data": company["es_data"],
            "response_string": corrected_information[0],
            "ner": new_ner,
        }

        return json.dumps(final_output)
    except:
        traceback.print_exc()


async def keypoint_checking(prompt, max_retries=3):
    for attempt in range(max_retries + 1):
        try:
            user_prompt = (
                VALID_QUERY_CHECKING_USER_PROMPT
                + f"""
                <Question>
                Query: {prompt}
                </Question>
                """
            )
            response = await invoke(
                messages=[
                    {"role": "system", "content": VALID_QUERY_CHECKING_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
                model="groq/llama-3.3-70b-versatile",
                fallbacks=["openai/gpt-4.1"],
            )
            verification = (
                response.split("<Response>")[1].split("</Response>")[0].strip()
            )
            return (
                json.dumps({"validQuery": True})
                if eval(verification)
                else json.dumps({"validQuery": False})
            )
        except Exception:
            if attempt == max_retries:
                return json.dumps({"validQuery": False})
            await asyncio.sleep(2**attempt)
