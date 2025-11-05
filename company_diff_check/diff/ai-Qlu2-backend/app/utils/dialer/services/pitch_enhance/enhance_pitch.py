from copy import deepcopy
from typing import Dict, Any

from app.utils.dialer.utils.gpt_utils.gpt_models import (
    GPT_COST_EFFICIENT_MODEL,
    GPT_MAIN_MODEL,
    GPT_BACKUP_MODEL,
)

from qutils.llm.asynchronous import invoke
from app.utils.dialer.services.live_pitch.live_pitch import live_pitch_converter
from app.utils.dialer.utils.gpt_utils.gpt_utils import getCallerName

from app.utils.dialer.services.pitch_enhance.enhance_pitch_prompts import (
    ENHANCE_HELPER_SYSTEM_PROMPT,
    ENHANCE_SYSTEM_PROMPT,
    ENHANCE_USER_PROMPT,
)


async def get_enhance_definitions(attributes: Dict[str, Any]) -> Dict[str, Any]:
    """
    Async Function to provide definitions for metrics that needs to be enhanced.

    Args:
    - attributes: Dictionary which contains metrics that are to be enhanced

    Returns:
    - dictionary: Metrics against definitions that would help gpt to enhance
    """
    systemPrompt = deepcopy(ENHANCE_HELPER_SYSTEM_PROMPT)
    userPrompt = """For the following attributes, figure out which needs a definition and return those in JSON format defined.
    Attributes: {attributes}
    """
    userPrompt = userPrompt.format(attributes=attributes)
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
    return response


async def enhance_pitch(
    text: str,
    metrics: Dict[str, Any],
    caller_name: str,
    callee_name: str,
    category: str,
) -> Dict[str, Any]:
    """
    Asynchronously enhances a given text based on specified attributes such as flattery, incentives, and call to action,
    for different communication channels. This function constructs a dynamic prompt for an AI model, which then generates
    a more persuasive or engaging message tailored to the callee's profile.

    Depending on the communication channel (e.g., LinkedIn connect or message), different attributes are emphasized in the
    enhancement process. For example, personalization might be emphasized more heavily in direct messages based on the
    detailed summary of the callee's profile.

    Parameters:
        text (str): The original text that needs to be enhanced.
        attributes (Dict[str, Any]): A dictionary containing various attributes (flattery, incentive, etc.) that guide
                                     how the text should be enhanced.
        caller_name (str): The name of the caller of the message.
        channel (str): The communication channel ('linkedin_connect', 'linkedin_message', etc.).
        category (str): The label of the message

    Returns:
        Dict[str, Any]: A dictionary containing the enhanced text. The key 'message' includes 'subject' (always None here)
                        and 'text', which is the enhanced message content.

    Raises:
        KeyError: If essential attributes are missing in the input dictionary.
    """

    text = text.strip()
    if text == "":
        return {"text": ""}

    callerName = await getCallerName(text)
    callerName = callerName["caller_name"]
    callerName = callerName.strip()
    callerName = callerName.strip("'")
    callerName = callerName.strip('"')

    if "[" in callerName and "]" in callerName:
        callerName = ""
    if callerName:
        caller_name = callerName

    system_prompt = deepcopy(ENHANCE_SYSTEM_PROMPT)
    user_prompt = deepcopy(ENHANCE_USER_PROMPT)
    user_prompt = user_prompt.format(
        text=text,
        caller_name=caller_name,  # , reference=len(text) + 200, category=category
    )

    """
    callee_data = attributes["profile_data"]
    profileName = None
    # print("callee_data: ", callee_data)
    # print("before profileName")
    if callee_data:
        if callee_data["fullName"] == "":
            profileName = callee_data["firstName"] + " " + callee_data["lastName"]
        else:
            profileName = callee_data["fullName"]
        name_data = await name_normalizer(profileName)
        title = ""
        if "Title" in name_data:
            if name_data["Title"]:
                title = name_data["Title"]
        if "firstName" in name_data:
            if name_data["firstName"]:
                profileName = title + " " + name_data["firstName"]

    # profileName = callee_data["firstName"]
    # print(f"Initial Attributes = {metrics}")
    callToAction = False
    personalization = False

    if "personalization" in metrics:
        personalization = metrics["personalization"]

    if "Personalization" in metrics:
        personalization = metrics["Personalization"]

    if "Personalisation" in metrics:
        personalization = metrics["Personalisation"]

    if "personalisation" in metrics:
        personalization = metrics["personalisation"]

    if "callToAction" in metrics:
        callToAction = metrics["callToAction"]

    # if callToAction:
        # user_prompt += f"Add the following call to action: {metrics['callToAction']}\n"
    # print("personalization: ", personalization)
    if personalization:
        if callee_data:
            summary_callee = await generate_summary(callee_data)
            print("callee's profile summary: ", summary_callee)
            user_prompt += (
                # "\nAdd personalized content to the cold call pitch based on the callee's profile summary: "
                "\nAdd one relevant business achievement from the callee's profile to the cold call pitch based on the callee's profile summary:"
                + summary_callee
                # + "\n But don't forget to keep the engagement level and your proposition."
            )
    if profileName:
        user_prompt += f"\n\nFor reference, the name of the callee is {profileName}"
    """

    if callee_name:
        user_prompt += f"\n\nFor reference, the name of the callee is {callee_name}"

    system_prompt = system_prompt.format(metrics=metrics)
    chat = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        enhanced_text = await invoke(
            messages=chat, temperature=0.1, model=GPT_MAIN_MODEL
        )
    except Exception as e:
        print(f"enhance_pitch primary call failed; falling back to backup model {e}")
        enhanced_text = await invoke(
            messages=chat, temperature=0.1, model=GPT_BACKUP_MODEL
        )

    enhanced_text = enhanced_text.strip()
    if enhanced_text != "":
        enhanced_text = await live_pitch_converter(enhanced_text)
        enhanced_text = enhanced_text.strip()

    if enhanced_text != "":
        return {"text": enhanced_text}
    else:
        return {"text": text}
