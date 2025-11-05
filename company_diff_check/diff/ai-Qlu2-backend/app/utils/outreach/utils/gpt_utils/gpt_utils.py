import os
import re
import json
import re
import asyncio
from typing import Tuple, List, Dict
from copy import deepcopy
from jaro import jaro_winkler_metric
from app.utils.outreach.utils.gpt_utils.gpt_runner import gpt_runner
from app.utils.outreach.utils.gpt_utils.gpt_utils_prompts import (
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
    SENDER_NAME_EXTRACTOR_SYSTEM_PROMPT,
    SENDER_NAME_EXTRACTOR_USER_PROMPT,
    EDUCATION_CHECKER_SYSTEM_PROMPT,
    EDUCATION_CHECKER_USER_PROMPT,
    CHECK_COMPANY_REFERENCE_SYSTEM_PROMPT,
    CHECK_COMPANY_REFERENCE_USER_PROMPT,
    CHECK_SUBJECT_PERSONALIZATION_SYSTEM_PROMPT,
    PERSONALIZATION_CHECKER_V2_SYSTEM_PROMPT,
    SENTIMENT_ANALYSIS_V2_SYSTEM_PROMPT,
)

OPEN_API_KEY = os.getenv("OPENAI_API_KEY")

GPT_MAIN_MODEL = "gpt-4.1"

GPT_COST_EFFICIENT_MODEL = "gpt-4o-mini"


def extract_placeholders(text):
    # Match anything inside square brackets: [ ... ]
    pattern = r"\[([^\[\]]+)\]"
    return re.findall(pattern, text)


def is_probably_url(text):
    text = text.lower()

    if (
        text.startswith("http://")
        or text.startswith("https://")
        or text.startswith("www.")
    ):
        return True

    domain_endings = (
        ".com",
        ".net",
        ".org",
        ".edu",
        ".gov",
        ".io",
        ".co",
        ".ai",
        ".pk",
        ".uk",
        ".de",
        ".cn",
    )
    if any(text.endswith(ext) for ext in domain_endings):
        return True

    if re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", text):
        return True

    return False


def extract_generic(start: str, end: str, text: str):
    """
    Extracts text between two specified delimiters using regular expressions.

    This function searches for text that appears between the start and end delimiters
    in the provided text string, handling multi-line content with the DOTALL flag.

    Args:
        start (str): The starting delimiter to search for
        end (str): The ending delimiter to search for
        text (str): The text to search within

    Returns:
        str or None: The extracted text if found, None otherwise
    """
    match = re.search(rf"{start}(.*?){end}", text, re.DOTALL)
    return match.group(1) if match else None


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

        isPersonalised = await gpt_runner(
            chat=chat, temperature=0.1, model="gpt-4o-mini"
        )

        isPersonalised = extract_generic(
            "<personalized>", "</personalized>", isPersonalised
        )
        if isPersonalised:
            if "yes" in isPersonalised.lower():
                isPersonalised = True
            else:
                isPersonalised = False
        else:
            isPersonalised = False
        # print(isPersonalised)
        return isPersonalised
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
        information = await gpt_runner(
            chat=chat, temperature=0.1, model="gpt-4.1", json_format=True
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
                companyName = exp.get("company_name", "")
                if companyName:
                    receiverCompanies.add(exp["company_name"].strip().lower())
                else:
                    companyName = exp.get("companyName", "")
                    if companyName:
                        receiverCompanies.add(exp["companyName"].strip().lower())

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

            company_comparison = await gpt_runner(
                chat=chat, temperature=0.1, model="gpt-4o-mini", json_format=True
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
        # print(company)
        return company, link, contactInfo
    except Exception as e:
        print(e)
        return company, link, contactInfo


async def gpt_reduce_length(text: str, character_length: int, tries=0) -> str:
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
    if tries < 1:
        system_prompt = f"""<task>
    You are an expert at reducing the character length of LinkedIn messages while ensuring context is retained.
    </task>

    <instructions>
    - **Goal:** Reduce the character count to be **270 characters or less**.
    - **Preserve Absolutely:** Retain all critical context, including:
    - Links (URLs). Do not alter or shorten the core URL.
    - Receiver's Name
    - Company Names
    - The main theme/intent of the message.
    - Sender's Details
    - **Shortening Method:** Achieve the goal by aggressively shortening non-critical text. Remove filler words, redundant phrases, and use common abbreviations where appropriate.
    - **Output:** Return only the new, shortened text. Do not provide any commentary.
    </instructions>"""
    else:
        system_prompt = f"""<task>
You are an expert at reducing the character length of LinkedIn messages. Your highest priority is to get the message to be 270 characters or less.
</task>

<instructions>
- **Absolute Priority:** The final output **must** be 270 characters or less.
- **Contingency Plan:** To meet this strict character limit, you could remove any long URL from the message (If any).
- **Context Replacement:** Replace the removed link with a concise, professional statement offering to share the link. Example phrases include: "I can share details upon request," or "Let me know if you'd like the brief."
- **Preserve Everything Else:** Ensure the receiver's name, the company name, sender's details and the core purpose of the message are all still in the final text.
- **Output:** Return only the new, shortened text. Do not provide any commentary.
</instructions>"""

    # system_prompt = f"""
    # You are an expert at reducing the text to less than {character_length - 30} characters but more than 100.
    # You will be given a text and you will reduce the character length of that text while maintaining the writing style.

    # You must strictly adhere to the following rules:
    # 1. Reduce the character length by summarizing the text.
    # 2. The new character length must be between 100-{character_length - 30} characters.
    # 3. The original writing style must be maintained
    # 4. Do not remove any links from the text. Links must retain at all cost.
    # 5. Do not remove any experience if mentioned in the original text
    # 6. Do Not alter or attempt to shorten any URL / link. If really necessary for concise communication, you may remove the preceeding part of https://www.
    # 7. Return only the new text.

    # **You must reduce the text no matter what**
    # """

    user_prompt = f"""<input_message>
{text}
</input_message>"""

    # if tries > 0:
    #     user_prompt += f"<CRITICAL> You already tried {tries+2} times, and failed, please make sure to return within limit now </CRITICAL>"
    chat = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        summarized_text = await gpt_runner(model="gpt-4.1", temperature=0.01, chat=chat)
    except Exception as e:
        print("got exception: ", e)
        summarized_text = await gpt_runner(model="gpt-4.1", temperature=0.2, chat=chat)
    return summarized_text, chat


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
    # system_prompt = """
    # You are an expert at removing personalization from texts and replacing it with placeholders.
    # You will be given a text that is being sent to someone.
    # Your task is to identify and remove personalization that applies specifically to the message receiver, while preserving any personal details, experiences, or identifiers that relate to the message sender.

    # Follow these guidelines:

    # 1. Replace any direct references to the receiver's personal details (e.g., name, location, job title) with generic placeholders (e.g., [Name], [Location], [Job Title], [Work Field]).
    # 2. Maintain any personalization that reflects the sender's perspective, including references to their own company name, experiences, skills, or industry knowledge.
    # 3. For any mentions of specific industries, companies, experiences, or skills that are not clearly attributed to the sender or receiver, use the placeholder [abc] to maintain neutrality.
    # 4. Do not remove urls or links, they are meant to stay.
    # 5. If the context makes it ambiguous whether the personalization is related to the sender or receiver, err on the side of de-personalization to protect the receiver's privacy.
    # 6. Use brackets [] to enclose placeholders and ensure they are easily identifiable in the text.

    # This approach ensures that the message is sanitized of personal details specific to the receiver while retaining the essence and personal touch from the sender's side.
    # """
    #     system_prompt = """
    # <role> You are an expert at removing receiver's personalization from texts and replacing it with placeholders </role>
    # <input>
    # - You will be given a text that is being sent to someone
    # </input>
    # <instructions>
    # 1. Strictly Replace any direct references to the receiver's personal details only (e.g., name, job title) with generic placeholders (e.g., [Name], [Location], [Job Title], [Work Field]).
    # 2. Maintain any personalization that reflects the sender's perspective, including references to their own company name, location ,experiences, skills, or industry knowledge.
    # 3 Maintain any mentions of specific company or job roles from sender that are not directly associated with receiver
    # 4. For any mentions of specific industries, companies, experiences, or skills that are not clearly attributed to the sender or receiver, use the placeholder [abc] to maintain neutrality.
    # 5. Do not remove urls or links, they are meant to stay.
    # 6. Use brackets [] to enclose placeholders and ensure they are easily identifiable in the text.
    # </instructions>
    # <output>
    # - Output your thought process, highlighting which fields are directly related to receiver and shall be removed enclosed within <reason> </reason> tags
    # - Next, output the final message with appropriate placeholders enclosed within the <placeholder_text> </placeholder_text>
    # </output>"""

    system_prompt = """<role> You are an expert at placing placeholders in messages </role>

<instructions>
- You'll be given a message as input
- The message might contain some personalized content about the receiver it was sent to
- This message is to be used as a template and thus it is important that any direct references to receiver's personal information (For example Name, Job, Location, Experience, Industry etc) must not be present in the template
- Personal content / statements are those which can help identify any personal trait of the receiver, for example their skills, company, industry etc which can not be sent to other candidates
- Your task is to replace such personal content with appropriate placeholders like [Name], [Location], [Domain] etc
- Use the most granular placeholder possible for each piece of information, and avoid altering the message content.
- It is equally important that only receiver's info is removed, all information that points towards Sender must stay
- All information and content that plays an important part in the context of the message for example a job role being offered, must stay
- All links must stay unless directly related to receiver (for example their portfolio)
- The message must remain the same, you can not alter anything in its structure apart from replacing receiver's data with placeholders []
</instructions>
<reasoning_steps>
- Think this way, 'Can this message be sent to anyone? across any industry? with any skills?' 
- You remove all such things that can't be sent to anyone and are user specific
</reasoning_steps>
<output>
- Output your step by step thought process, highlighting which fields are directly related to receiver and shall be removed enclosed within <reason> </reason> tags
- Next, output the final message with appropriate placeholders enclosed within the <placeholder_text> </placeholder_text>
</output> 
<example_input>
Hi Akhlaq, your experience at QLU.ai, your degree from Sukkur IBA, and your skills in React, Next.js, and PostgreSQL make you an ideal person to talk to.
</example_input>
<good_example>
Hi [Name], your experience at [Company], your degree from [Institute], and your skills in [Relevant Skills] make you an ideal person to talk to.
</good_example>
<bad_example>
Hi [Name], [Previous_Employer], [Degree] from [University], and [Skills] make you an ideal person to talk to.
</bad_example>"""
    chat = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": text,
        },
    ]
    response = await gpt_runner(
        model="gpt-4.1", temperature=0.01, chat=chat, json_format=False
    )
    reason = extract_generic("<reason>", "</reason>", response)
    placeholder_text = extract_generic(
        "<placeholder_text>", "</placeholder_text>", response
    )
    return placeholder_text


async def name_normalizer(fullname: str) -> str:
    systemPrompt = deepcopy(NAME_NORMALIZER_SYSTEM_PROMPT)
    chat = [
        {"role": "system", "content": systemPrompt},
        {"role": "user", "content": fullname},
    ]
    name_data = await gpt_runner(chat, 0.1, "gpt-4o-mini", True)
    name_data = json.loads(name_data)
    # name_data = await name_normalizer(profileName)
    # print(name_data)
    profileName = fullname
    title = ""
    if "Title" in name_data:
        if name_data["Title"]:
            title = name_data["Title"]
    if "firstName" in name_data:
        if name_data["firstName"]:
            profileName = title + " " + name_data["firstName"]
    profileName = profileName.strip()
    profileName = profileName.strip('"')
    profileName = profileName.strip("'")
    return profileName


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

    response = await gpt_runner(
        model="gpt-4o-mini", temperature=0.2, chat=chat, json_format=False
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
    if len(msgList) > 5:
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

    response = await gpt_runner(
        model="gpt-4o-mini", temperature=0.1, chat=chat, json_format=True
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
        result["isInterested"] = True

    return result


async def closingChecker(msg: str) -> str:
    systemPrompt = deepcopy(CLOSING_CHECKER_SYSTEM_PROMPT)
    userPrompt = deepcopy(CLOSING_CHECKER_USER_PROMPT)

    userPrompt = userPrompt.format(message=msg)

    chat = [
        {"role": "system", "content": systemPrompt},
        {"role": "user", "content": userPrompt},
    ]

    response = await gpt_runner(
        chat=chat, model="gpt-4o-mini", temperature=0.1, json_format=True
    )
    response = json.loads(response)

    response["substring"] = response["substring"].strip()
    response["substring"] = response["substring"].strip('"')
    response["substring"] = response["substring"].strip("'")

    if not response["closing"]:
        response["substring"] = ""

    return response


async def getSenderName(msg: str) -> dict:
    systemPrompt = deepcopy(SENDER_NAME_EXTRACTOR_SYSTEM_PROMPT)
    userPrompt = deepcopy(SENDER_NAME_EXTRACTOR_USER_PROMPT)
    userPrompt = userPrompt.format(message=msg)

    chat = [
        {"role": "system", "content": systemPrompt},
        {"role": "user", "content": userPrompt},
    ]
    response = await gpt_runner(
        chat, temperature=0.1, model="gpt-4o-mini", json_format=True
    )
    return json.loads(response)


async def checkEducation(reference: str) -> bool:
    systemPrompt = deepcopy(EDUCATION_CHECKER_SYSTEM_PROMPT)
    userPrompt = deepcopy(EDUCATION_CHECKER_USER_PROMPT)

    userPrompt = userPrompt.format(reference=reference)

    chat = [
        {"role": "system", "content": systemPrompt},
        {"role": "user", "content": userPrompt},
    ]

    response = await gpt_runner(
        chat=chat, temperature=0.1, model="gpt-4o-mini", json_format=True
    )
    response = json.loads(response)

    return response


async def checkCompanyReference(reference: str):
    systemPrompt = deepcopy(CHECK_COMPANY_REFERENCE_SYSTEM_PROMPT)
    userPrompt = deepcopy(CHECK_COMPANY_REFERENCE_USER_PROMPT)

    userPrompt = userPrompt.format(message=reference)

    chat = [
        {"role": "system", "content": systemPrompt},
        {"role": "user", "content": userPrompt},
    ]

    response = await gpt_runner(
        chat=chat, temperature=0.1, model="gpt-4o-mini", json_format=True
    )
    response = json.loads(response)

    companyReference = set()
    for i in response["referenced"]:
        if i.lower() == "company goals":
            companyReference.add("About Company")
        else:
            companyReference.add(i)
    return companyReference


async def check_subject_personalization(subject: str, message: str) -> bool:
    systemPrompt = deepcopy(CHECK_SUBJECT_PERSONALIZATION_SYSTEM_PROMPT)
    userPrompt = f"""<email_subject> {subject} </email_subject>
<email_body> {message} </email_body>"""

    chat = [
        {"role": "system", "content": systemPrompt},
        {"role": "user", "content": userPrompt},
    ]

    tasks = []

    for i in range(2):
        tasks.append(gpt_runner(chat=chat, temperature=0.1, model="gpt-4.1-mini"))

    responses = await asyncio.gather(*tasks)
    true_responses = 0
    false_responses = 0
    for response in responses:
        verdict = extract_generic("<verdict>", "</verdict>", response)
        placeholder_subject = extract_generic(
            "<placeholder_subject>", "</placeholder_subject>", response
        )
        if "true" in verdict.lower():
            true_responses += 1
        else:
            false_responses += 1
    if false_responses == 2:

        return False, subject
    return True, placeholder_subject


async def personalization_checker_v2(message: str) -> bool:
    systemPrompt = deepcopy(PERSONALIZATION_CHECKER_V2_SYSTEM_PROMPT)
    userPrompt = """<message> {message} </message>"""

    userPrompt = userPrompt.format(message=message)

    chat = [
        {"role": "system", "content": systemPrompt},
        {"role": "user", "content": userPrompt},
    ]

    response = await gpt_runner(chat=chat, temperature=0.1, model="gpt-4.1")

    isPersonalized = extract_generic(
        "<is_personalized>", "</is_personalized>", response
    )
    placeholder_text = extract_generic(
        "<placeholder_text>", "</placeholder_text>", response
    )

    if "yes" in isPersonalized.lower().strip():
        return {"isPersonalized": True, "placeholder_text": placeholder_text}
    return {"isPersonalized": False, "placeholder_text": message}


async def sentiment_analysis_v2(conversation: List[Dict[str, str]]) -> bool:
    system_prompt = deepcopy(SENTIMENT_ANALYSIS_V2_SYSTEM_PROMPT)

    user_prompt = ""
    for msg in conversation:
        if "Sender" in msg:
            user_prompt += f"<sender>\n{msg['Sender']}\n</sender>\n"
        else:
            user_prompt += f"<receiver>\n{msg['Receiver']}\n</receiver>\n"
    user_prompt = f"<conversation>\n{user_prompt}</conversation>"

    chat = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = await gpt_runner(chat=chat, temperature=0.1, model="gpt-4.1-mini")

    reason = extract_generic("<reason>", "</reason>", response)
    category = extract_generic("<category>", "</category>", response)

    return {
        "reason": reason,
        "category": category,
    }
