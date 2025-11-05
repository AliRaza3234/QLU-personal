import asyncio
import json
from app.utils.outreach.services.modify_text.modification_prompts import (
    MODIFY_NON_LICONNET_SYSTEM_PROMPT,
    MODIFY_NON_LICONNET_USER_PROMPT,
    MODIFY_MESSAGE_SYSTEM_PROMPT,
    MODIFY_MESSAGE_USER_PROMPT,
)
import re
from copy import deepcopy

from app.utils.outreach.utils.gpt_utils.gpt_runner import gpt_runner
from app.utils.outreach.utils.gpt_utils.gpt_utils import (
    gpt_reduce_length,
    name_normalizer,
    getSenderName,
)


async def modify_text(
    text: str,
    modification_type: str,
    sender_name: str,
    receiver_name: str,
    channel: str,
) -> str:
    """
    Async Function to modify a piece of text based on the modification type defined.

    Args:
    - text (str): Text that needs to be modified
    - modification_type (str): Type of modification required example 'longer', 'shorter' etc
    - sender_name (str): Name of the message sender
    - receiver_name (str): Name of the message receiver
    - channel (str): Channel of communication such as linkedin_premium, mail etc

    Returns:
    - Modified Message (str): Modified message
    """

    receiver_name, senderName = await asyncio.gather(
        *[name_normalizer(receiver_name), getSenderName(text)]
    )
    senderName = senderName["sender_name"]
    senderName = senderName.strip()
    senderName = senderName.strip("'")
    senderName = senderName.strip('"')

    if "[" in senderName and "]" in senderName:
        senderName = ""

    sender_flag = False
    if senderName:
        sender_flag = True
        sender_name = senderName

    # print(receiver_name)

    character_length = 160 if channel == "linkedin_connect" else 260
    if channel != "linkedin_connect" and channel != "linkedin_premium":
        # print("hereee")
        system_prompt_modify_text = deepcopy(MODIFY_NON_LICONNET_SYSTEM_PROMPT)
        user_prompt = deepcopy(MODIFY_NON_LICONNET_USER_PROMPT)
        if (
            "professional" in modification_type
            or "simpler" in modification_type
            or "casual" in modification_type
        ):
            user_prompt = user_prompt.format(
                text=text,
                modification_type=modification_type,
                sender_name=sender_name,
                receiver_name=receiver_name,
            )
            user_prompt += f"Strictly maintain a character length of {len(text)}"
        else:
            user_prompt = user_prompt.format(
                text=text,
                modification_type=modification_type,
                sender_name=sender_name,
                receiver_name=receiver_name,
            )
        # print(user_prompt)
    else:
        system_prompt_modify_text = deepcopy(MODIFY_MESSAGE_SYSTEM_PROMPT)
        user_prompt = deepcopy(MODIFY_MESSAGE_USER_PROMPT)

        user_prompt = user_prompt.format(
            character_limit=character_length,
            text=text,
            modification_type=modification_type,
            sender_name=sender_name,
            receiver_name=receiver_name,
        )

    if sender_flag:
        user_prompt += f" and the sender name to use in salutation is {sender_name}"
    else:
        user_prompt += f" and the sender name is {sender_name}"

    chat = [
        {"role": "system", "content": system_prompt_modify_text},
        {
            "role": "user",
            "content": user_prompt
            + "<Important Info> Make sure that you format the message with appropriate new lines when neccssary </Important Info>",
        },
    ]
    # print(len(text))
    response = await gpt_runner(
        chat=chat, temperature=0.5, model="gpt-4.1", json_format=True
    )

    response = json.loads(response)
    response = response["response"]

    # print(len(response))
    if (channel == "linkedin_connect" or channel == "linkedin_premium") and len(
        response
    ) > character_length + 39:
        loop_count = 0
        while len(response) > character_length + 39:
            if loop_count >= 5:
                break
            response, chat_ = await gpt_reduce_length(
                response, character_length, loop_count
            )
            response = response.replace('"', "")
            loop_count += 1
            # print(len(response))

        # response = await gpt_reduce_length(response, character_length=character_length)
    response = re.sub(r"^Subject:.*\n", "", response, flags=re.MULTILINE)
    return {"message": {"modified_response": response}}
