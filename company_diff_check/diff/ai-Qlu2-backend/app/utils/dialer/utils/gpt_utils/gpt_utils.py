import os
import re
import json
from typing import Tuple, List, Dict
from copy import deepcopy
from jaro import jaro_winkler_metric

from qutils.llm.asynchronous import invoke
from app.utils.dialer.utils.gpt_utils.gpt_utils_prompts import (
    PERSONALISED_CHECKER_SYSTEM_PROMPT,
    PERSONALISED_CHECKER_USER_PROMPT,
    INFORMATION_EXTRACTION_USER_PROMPT,
    INFORMATION_EXTRACTION_SYSTEM_PROMPT_2,
    NAME_NORMALIZER_SYSTEM_PROMPT,
    SENTIMENT_ANALYSIS_USER_PROMPT,
    SENTIMENT_ANALYSIS_SYSTEM_PROMPT,
    COVERSATION_SUMMARY_USER_PROMPT,
    COVERSATION_SUMMARY_SYSTEM_PROMPT,
    SENTIMENT_ANALYSIS_SUMMARY_SYSTEM_PROMPT,
    SENTIMENT_ANALYSIS_SUMMARY_USER_PROMPT,
    CLOSING_CHECKER_SYSTEM_PROMPT,
    CLOSING_CHECKER_USER_PROMPT,
    COMPANY_COMPARISON_SYSTEM_PROMPT,
    COMPANY_COMPARISON_USER_PROMPT,
    CALLER_NAME_EXTRACTOR_SYSTEM_PROMPT,
    CALLER_NAME_EXTRACTOR_USER_PROMPT,
    CALLEE_NAME_EXTRACTOR_SYSTEM_PROMPT,
    CALLEE_NAME_EXTRACTOR_USER_PROMPT,
    POST_SF_SYS_PROMPT,
    POST_SF_USER_PROMPT,
    SUBJECT_SYS_PROMPT,
    SUBJECT_USER_PROMPT,
    NER_SYS_PROMPT,
)

from app.utils.dialer.utils.gpt_utils.gpt_models import (
    GPT_COST_EFFICIENT_MODEL,
    GPT_MAIN_MODEL,
)


async def subject_generator(text: str) -> str:
    """
    Async function generates a subject for the given input text
    """

    sys_prompt = deepcopy(SUBJECT_SYS_PROMPT)
    user_prompt = deepcopy(SUBJECT_USER_PROMPT)

    user_prompt = user_prompt.format(text)
    subject_chat = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt},
    ]
    response = ""
    try:
        response = await invoke(
            messages=subject_chat, temperature=0.1, model=GPT_COST_EFFICIENT_MODEL
        )
    except Exception as e:
        print(e)
        response = await invoke(
            messages=subject_chat, temperature=0.3, model=GPT_MAIN_MODEL
        )
    return response


async def sentence_formatter(text: str) -> list:
    """
    Async function to format input text into structured complete sentences using an AI model.

    Args:
    - text (str): The input text to be formatted.

    Returns:
    - list: A list of sentences formatted by the AI model.
    """

    sys_prompt = deepcopy(POST_SF_SYS_PROMPT)
    user_prompt = deepcopy(POST_SF_USER_PROMPT)
    user_prompt = user_prompt.format(text)

    chat = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = await invoke(
        messages=chat,
        temperature=0.1,
        model=GPT_COST_EFFICIENT_MODEL,
        response_format={"type": "json_object"},
    )
    response = json.loads(response)
    return response["sentences"]


async def ner_on_text(text: str) -> dict:
    ner_output_payload = {}
    if text == "":
        ner_output_payload["ner_result"] = None
        return ner_output_payload

    sys_prompt = deepcopy(NER_SYS_PROMPT)

    ner_chat = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": text},
    ]
    summary_response = await invoke(
        messages=ner_chat,
        temperature=0,
        model=GPT_COST_EFFICIENT_MODEL,
        response_format={"type": "json_object"},
    )
    summary_response = json.loads(summary_response)

    print("summary_response: ", summary_response)
    if summary_response["companies"] == []:
        return {"data": None}
    companies = summary_response["companies"]

    companies_ner_result = {}
    for company in companies:
        # occurances = [m.start() for m in re.finditer(company.lower(), summary.lower())]
        occurances = [m.start() for m in re.finditer(company, text)]
        for occur in occurances:
            companies_ner_result[str(occur)] = company

    ner_output_payload["ner_result"] = companies_ner_result
    return ner_output_payload


# -----------------------------------------------------------------------------------------#


async def personalisation_checker(text: str) -> bool:
    """
    Async function to check, given a piece of text, whether it includes personalised content
    such as past experiences etc

    Args:
    - Text (str): The message which has to be checked for personalised content

    Returns:
    - Bool: True if has personalised content, False otherwise
    """
    systemPrompt = deepcopy(PERSONALISED_CHECKER_SYSTEM_PROMPT)
    userPrompt = deepcopy(PERSONALISED_CHECKER_USER_PROMPT)
    userPrompt = userPrompt.format(text=text)
    chat = [
        {"role": "system", "content": systemPrompt},
        {"role": "user", "content": userPrompt},
    ]
    try:
        isPersonalised = await invoke(
            messages=chat,
            temperature=0.1,
            model=GPT_MAIN_MODEL,
            response_format={"type": "json_object"},
        )

        isPersonalised = json.loads(isPersonalised)
        if "personalised" in isPersonalised:
            isPersonalised["Personalised"] = isPersonalised["personalised"]

        return isPersonalised["Personalised"]
    except Exception as e:
        return e


async def information_extractor(
    text: str, profileData: dict = None
) -> Tuple[str, str, str]:
    """
    Async function to extract information from a piece of text. This information include:
    - Company Names
    - Links
    - Contact Information

    Args:
    - Text (str): The message from which information has to be extracted from

    Returns:
    - Tuple of company, link, contactInfo
    """
    systemPrompt = deepcopy(INFORMATION_EXTRACTION_SYSTEM_PROMPT_2)
    userPrompt = deepcopy(INFORMATION_EXTRACTION_USER_PROMPT)
    userPrompt = userPrompt.format(text=text)
    chat = [
        {"role": "system", "content": systemPrompt},
        {"role": "user", "content": userPrompt},
    ]
    try:
        information = await invoke(
            messages=chat,
            temperature=0.1,
            model=GPT_MAIN_MODEL,
            response_format={"type": "json_object"},
        )
        company = ""
        link = ""
        contactInfo = ""
        information = json.loads(information)
        # print(information)
        if "company" in information:
            information["Company"] = information["company"]
        if "links" in information:
            information["Links"] = information["links"]
        if "contact" in information:
            information["Contact"] = information["contact"]

        if profileData:
            receiverCompanies = set()
            for exp in profileData["_source"]["experience"]:
                if exp["company_name"]:
                    receiverCompanies.add(exp["company_name"].strip().lower())

            # print(receiverCompanies)
            # print(information["Company"])

            tempList = []
            for companies in information["Company"]:
                tempBool = False
                if companies[1] == "Neutral" or companies[1] == "neutral":
                    for receiverCompany in receiverCompanies:
                        if (
                            jaro_winkler_metric(
                                receiverCompany, companies[0].strip().lower()
                            )
                            >= 0.92
                        ):
                            tempBool = True
                if tempBool:
                    continue
                if companies[1] == "Neutral" or companies[1] == "neutral":
                    tempList.append(companies[0])

            systemPrompt = deepcopy(COMPANY_COMPARISON_SYSTEM_PROMPT)
            userPrompt = deepcopy(COMPANY_COMPARISON_USER_PROMPT)
            userPrompt = userPrompt.format(existing=receiverCompanies, entered=tempList)
            chat = [
                {"role": "system", "content": systemPrompt},
                {"role": "user", "content": userPrompt},
            ]

            company_comparison = await invoke(
                messages=chat,
                temperature=0.1,
                model=GPT_COST_EFFICIENT_MODEL,
                response_format={"type": "json_object"},
            )
            company_comparison = json.loads(company_comparison)

            if "Companies" in company_comparison:
                company_comparison["companies"] = company_comparison["Companies"]

            if company_comparison["companies"]:
                company_comparison["companies"] = [
                    [i, "Neutral"] for i in company_comparison["companies"]
                ]

            for companies in information["Company"]:
                if companies[1] == "Sender" or companies[1] == "sender":
                    company_comparison["companies"].append(companies)

            information["Company"] = deepcopy(company_comparison["companies"])

        for companies in information["Company"]:
            if companies[1] != "Receiver" and companies[1] != "receiver":
                company += companies[0] + "\n"
        for url in information["Links"]:
            link += url[0] + "\n"
        for contact in information["Contact"]:
            if contact[1] != "Receiver" and contact[1] != "receiver":
                contactInfo += contact[0] + "\n"

        # print(information["Company"])

        company = company.strip("\n")
        link = link.strip("\n")
        contactInfo = contactInfo.strip("\n")
        return company, link, contactInfo
    except Exception as e:
        print(e)
        return company, link, contactInfo


async def gpt_reduce_length(text: str, character_length: int) -> str:
    """
    Asynchronously generates a summary of a given text, adhering to specific summarization rules and style constraints.

    This function utilizes a GPT-based model to reduce the length of the input text to less than 180 characters while preserving the original writing style of the text. It sends a structured chat prompt to the model, specifying the rules for summarization, and handles the model's response.

    Parameters:
        text (str): The text to be summarized.

    Returns:
        str: A summary of the input text, constrained to less than 170 characters and maintaining the original writing style.

    Raises:
        Exception: Outputs an error message and retries summarization with a simpler model configuration if the initial attempt fails.

    Note:
        The function is designed to first attempt summarization with a specific GPT model and, upon failure, falls back to a simpler model.
    """
    system_prompt = f"""
    You are an expert at reducing the text to less than {character_length - 40} characters but more than 100.
    You will be given a text and you will reduce the character length of that text while maintaining the writing style.

    You must strictly adhere to the following rules:
    1. Reduce the character length by summarizing the text.
    2. The new character length must be between 100-{character_length - 40} characters.
    3. The writing style must be maintained in the new text.
    4. Do not remove any links from the text. Links must retain at all cost.
    5. Do Not alter or attempt to shorten any URL / link. If really necessary for concise communication, you may remove the preceeding part of https://www.
    6. Return only the new text.

    **You must reduce the text no matter what**
    """

    user_prompt = f"""
    Reduce the following text between 100-{character_length - 30} characters:
    {text}
    """
    chat = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        summarized_text = await invoke(
            messages=chat, temperature=0.1, model=GPT_MAIN_MODEL
        )
    except Exception as e:
        print("got exception: ", e)
        summarized_text = await invoke(
            messages=chat, temperature=0.2, model=GPT_MAIN_MODEL
        )
    return summarized_text


async def personalization_remover(text: str) -> str:
    """
    Asynchronously removes personalization from a given text that is directed towards someone else,
    replacing it with generic placeholders while maintaining any personal details related to the sender.

    This function leverages a GPT-based model to identify and remove any personalized content in the text
    that specifically relates to the receiver of the message. It converts these personalized references
    into generic placeholders like [Name], [Location], or [Job Title], ensuring privacy and neutrality.
    The function preserves personalization related to the sender, such as references to the sender's
    experiences, skills, or industry knowledge.

    Parameters:
        text (str): The text from which personalization needs to be removed.

    Returns:
        str: The sanitized text with receiver-specific personalization replaced by placeholders,
             while sender-specific details are retained.

    Note:
        The function uses a structured prompt with specific rules to guide the model in removing personalization
        effectively, ensuring the neutrality and privacy of the intended message receiver are maintained.
    """
    # print("HERERERE")
    system_prompt = """
    You are an expert at removing personalization from texts and replacing it with placeholders. 
    You will be given a text that is being sent to someone. 
    Your task is to identify and remove personalization that applies specifically to the message receiver, while preserving any personal details, experiences, or identifiers that relate to the message sender.

    Follow these guidelines:

    1. Replace any direct references to the receiver's personal details (e.g., name, location, job title) with generic placeholders (e.g., [Name], [Location], [Job Title], [Work Field]).
    2. Maintain any personalization that reflects the sender's perspective, including references to their own company name, experiences, skills, or industry knowledge.
    3. For any mentions of specific industries, companies, experiences, or skills that are not clearly attributed to the sender or receiver, use the placeholder [abc] to maintain neutrality.
    4. Do not remove urls or links, they are meant to stay.
    5. If the context makes it ambiguous whether the personalization is related to the sender or receiver, err on the side of de-personalization to protect the receiver's privacy.
    6. Use brackets [] to enclose placeholders and ensure they are easily identifiable in the text.

    This approach ensures that the message is sanitized of personal details specific to the receiver while retaining the essence and personal touch from the sender's side.
    """
    chat = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": "For text: "
            + text
            + ".\nDo not remove links and urls, let them be in original state.\nDo not remove any sender side personalization",
        },
    ]
    response = await invoke(messages=chat, temperature=0.2, model=GPT_MAIN_MODEL)
    return response


async def name_normalizer(fullname: str) -> str:
    systemPrompt = deepcopy(NAME_NORMALIZER_SYSTEM_PROMPT)
    chat = [
        {"role": "system", "content": systemPrompt},
        {"role": "user", "content": fullname},
    ]
    response = await invoke(
        messages=chat,
        temperature=0.1,
        model=GPT_COST_EFFICIENT_MODEL,
        response_format={"type": "json_object"},
    )
    return json.loads(response)


async def conversationSummary(conversation: List[Dict[str, str]]) -> str:
    """
    Async function to perform conversation summary which would be later used to perform
    Sentiment Analysis.

    Arguments:
    - conversation: List of messages in order

    Returns:
    - Summary: string
    """
    systemPrompt = deepcopy(COVERSATION_SUMMARY_SYSTEM_PROMPT)
    userPrompt = deepcopy(COVERSATION_SUMMARY_USER_PROMPT)

    messages = ""
    for msg in conversation:
        for user in msg:
            messages += f"{user}: {msg[user]}\n"
    messages = messages.strip("\n")

    userPrompt = userPrompt.format(conversation=messages)

    chat = [
        {"role": "system", "content": systemPrompt},
        {"role": "user", "content": userPrompt},
    ]

    response = await invoke(
        messages=chat, temperature=0.2, model=GPT_COST_EFFICIENT_MODEL
    )
    response = response.strip()
    response = response.strip("'")
    response = response.strip('"')

    return response


async def sentimentAnalysis(msgList: List[str]) -> Dict[str, int]:
    """
    Async function to perform sentiment analysis on a list of messages.

    Arguments:
    - conversation: List of messages in order

    Returns:
    - Summary: string
    """
    summary = ""
    messages = ""
    if len(msgList) > 3:
        systemPrompt = deepcopy(SENTIMENT_ANALYSIS_SUMMARY_SYSTEM_PROMPT)
        userPrompt = deepcopy(SENTIMENT_ANALYSIS_SUMMARY_USER_PROMPT)
        summary = await conversationSummary(msgList)
    else:
        messages = ""
        for msg in msgList:
            for user in msg:
                messages += f"{user}: {msg[user]}\n"
        messages = messages.strip("\n")
        systemPrompt = deepcopy(SENTIMENT_ANALYSIS_SYSTEM_PROMPT)
        userPrompt = deepcopy(SENTIMENT_ANALYSIS_USER_PROMPT)

    userPrompt = userPrompt.format(
        message=msgList[0]["Sender"], summary=summary, conversation=messages
    )

    chat = [
        {"role": "system", "content": systemPrompt},
        {"role": "user", "content": userPrompt},
    ]

    response = await invoke(
        messages=chat,
        temperature=0.1,
        model=GPT_COST_EFFICIENT_MODEL,
        response_format={"type": "json_object"},
    )
    response = json.loads(response)
    thought = response["Thought"]
    decision = response["Decision"]

    ENV = os.getenv("ENVIRONMENT")
    if ENV == "production":
        result = {"isInterested": False}
    else:
        result = {"isInterested": False, "thought": thought}

    if decision == "0" or decision == 0:
        result["isInterested"] = False
    elif decision == "1" or decision == 1:
        result["isInterested"] = True
    else:
        result["isInterested"] = False

    return result


async def closingChecker(msg: str) -> str:
    systemPrompt = deepcopy(CLOSING_CHECKER_SYSTEM_PROMPT)
    userPrompt = deepcopy(CLOSING_CHECKER_USER_PROMPT)

    userPrompt = userPrompt.format(message=msg)

    chat = [
        {"role": "system", "content": systemPrompt},
        {"role": "user", "content": userPrompt},
    ]

    response = await invoke(
        messages=chat,
        temperature=0.1,
        model=GPT_COST_EFFICIENT_MODEL,
        response_format={"type": "json_object"},
    )
    response = json.loads(response)

    # print(response)

    response["substring"] = response["substring"].strip()
    response["substring"] = response["substring"].strip('"')
    response["substring"] = response["substring"].strip("'")

    if not response["closing"]:
        response["substring"] = ""

    return response


async def getCallerName(pitch: str) -> dict:
    systemPrompt = deepcopy(CALLER_NAME_EXTRACTOR_SYSTEM_PROMPT)
    userPrompt = deepcopy(CALLER_NAME_EXTRACTOR_USER_PROMPT)
    userPrompt = userPrompt.format(pitch=pitch)

    chat = [
        {"role": "system", "content": systemPrompt},
        {"role": "user", "content": userPrompt},
    ]
    response = await invoke(
        messages=chat,
        temperature=0.1,
        model=GPT_COST_EFFICIENT_MODEL,
        response_format={"type": "json_object"},
    )
    return json.loads(response)


async def getCalleeName(pitch: str) -> dict:
    systemPrompt = deepcopy(CALLEE_NAME_EXTRACTOR_SYSTEM_PROMPT)
    userPrompt = deepcopy(CALLEE_NAME_EXTRACTOR_USER_PROMPT)
    userPrompt = userPrompt.format(pitch=pitch)

    chat = [
        {"role": "system", "content": systemPrompt},
        {"role": "user", "content": userPrompt},
    ]
    response = await invoke(
        messages=chat,
        temperature=0.1,
        model=GPT_COST_EFFICIENT_MODEL,
        response_format={"type": "json_object"},
    )
    return json.loads(response)
