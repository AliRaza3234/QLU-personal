import os
import re
from typing import List, Dict, Any


from qutils.llm.asynchronous import invoke


ENV = os.getenv("ENVIRONMENT")


def extract_json(text):
    match = re.search(r"```json(.*?)```", text, re.DOTALL)
    return match.group(1) if match else text


async def gpt_runner(
    chat: List[Dict[str, Any]],
    temperature: float,
    model: str,
    json_format=False,
    provider: str = "openai",
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

    prefill_string = ""

    model_mapping = {
        "claude-3.7-sonnet": {
            "model": "anthropic/claude-3-7-sonnet-latest",
        },
        "claude-3.5-sonnet": {
            "model": "anthropic/claude-3-5-sonnet-latest",
        },
        "claude-3.5-haiku": {
            "model": "anthropic/claude-3-5-haiku-latest",
        },
        "gpt-4o-mini": {
            "model": "openai/gpt-4o-mini",
        },
        "gpt-4.1-mini": {
            "model": "openai/gpt-4.1-mini",
        },
        "gpt-4.1": {
            "model": "openai/gpt-4.1",
        },
        "gpt-4o": {
            "model": "openai/gpt-4o",
        },
        "llama-3.3-70b-versatile": {
            "model": "groq/llama-3.3-70b-versatile",
        },
        "gpt-oss-120b": {
            "model": "groq/openai/gpt-oss-120b",
        },
        "gpt-oss-20b": {
            "model": "groq/openai/gpt-oss-20b",
        },
    }

    if ENV != "production":
        if "gpt-4o" in model and "mini" not in model:
            model = "gpt-4.1"

    if "claude" in model and json_format:
        prefill_string = "```json"
        chat.append({"role": "assistant", "content": prefill_string})

    if json_format:
        res = await invoke(
            messages=chat,
            temperature=temperature,
            model=model_mapping[model]["model"],
            response_format={"type": "json_object"},
        )
    else:
        res = await invoke(
            messages=chat,
            temperature=temperature,
            model=model_mapping[model]["model"],
        )

    if prefill_string:
        res = extract_json(prefill_string + res)

    return res
