import time
import os
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI, OpenAI

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")


def direct_gpt_runner(
    chat: List[Dict[str, Any]], temperature: float, model: str, json_format=False
) -> str:
    """
    Asynchronously sends a chat prompt to an OpenAI model and retrieves the generated response.

    This function interfaces with the OpenAI API to submit chat messages and get responses from a specified model.
    It configures the conversation using a predefined temperature setting, which affects the randomness of the response.
    After generating the response, the function closes the API client connection and extracts the primary response
    message from the received data.

    Parameters:
    chat (List[Dict[str, Any]]): A list of dictionaries where each dictionary represents a single message in the conversation,
    typically including keys like 'role' and 'content'.
    temperature (float): A float indicating the randomness of the response. Lower values make the model's responses more deterministic.
    model (str): The identifier of the OpenAI model to use for generating responses.

    Returns:
    str: The content of the first message in the model's response. This is typically what you would display back to a user in a chat interface.

    Note:
    - This function assumes that the API key is correctly set in the 'OPEN_API_KEY' environment variable.
    - Ensure proper error handling in production use, especially for network issues and API limits.
    """
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
    # print(model,"MODEL")
    model_to_use = model if "/" in model else f"openai/{model}"
    if json_format:
        response = client.chat.completions.create(
            model=model_to_use,
            messages=chat,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
    else:
        response = client.chat.completions.create(
            model=model_to_use, messages=chat, temperature=temperature
        )
    client.close()
    # model_name = response.model
    # input_tokens = response.usage.prompt_tokens
    # output_tokens = response.usage.completion_tokens
    return response.choices[0].message.content


import asyncio


async def gpt_runner(
    chat: List[Dict[str, Any]],
    temperature: float,
    model: str,
    json_format=False,
    timeout: Optional[int] = None,
) -> str:
    """
    Asynchronously sends a chat prompt to an OpenAI model with an optional timeout.

    Parameters:
    - chat (List[Dict[str, Any]]): A list of dictionaries where each dictionary represents a single message in the conversation.
    - temperature (float): A float indicating the randomness of the response.
    - model (str): The identifier of the OpenAI model to use.
    - json_format (bool): Whether to return the response in JSON format.
    - timeout (Optional[int]): Maximum time in seconds to wait for the response. If None, no timeout is applied.

    Returns:
    - str: The content of the first message in the model's response.
    """
    aclient = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY
    )
    model_to_use = model if "/" in model else f"openai/{model}"
    try:
        if json_format:
            if timeout:
                response = await asyncio.wait_for(
                    aclient.chat.completions.create(
                        model=model_to_use,
                        messages=chat,
                        temperature=temperature,
                        response_format={"type": "json_object"},
                    ),
                    timeout=timeout,
                )
            else:
                response = await aclient.chat.completions.create(
                    model=model_to_use,
                    messages=chat,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                )
        else:
            if timeout:
                response = await asyncio.wait_for(
                    aclient.chat.completions.create(
                        model=model_to_use, messages=chat, temperature=temperature
                    ),
                    timeout=timeout,
                )
            else:
                response = await aclient.chat.completions.create(
                    model=model_to_use, messages=chat, temperature=temperature
                )
    except asyncio.TimeoutError:
        await aclient.close()
        return "Request timed out"

    await aclient.close()

    # model_name = response.model
    # input_tokens = response.usage.prompt_tokens
    # output_tokens = response.usage.completion_tokens

    return response.choices[0].message.content
