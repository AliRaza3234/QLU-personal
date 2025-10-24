import re
import traceback

from qutils.llm.asynchronous import invoke
from app.utils.search.aisearch.company.generation.prompts import (
    DAMN_SHORTEN_PROMPT_CLAUDE,
    DAMN_SHORTEN_PROMPT_CLAUDE_NEW,
)


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


async def dual_shorten_prompt(prompt, use_legacy_prompt=True):
    if use_legacy_prompt:
        messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": DAMN_SHORTEN_PROMPT_CLAUDE}],
            },
            {
                "role": "assistant",
                "content": [{"type": "text", "text": "Yes, I understand."}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""\n<Query>\n\n{prompt}\n</Query>\n\nAlso explain how you are following the Company Prompts Construction Guidelines and the Company Naming Conventions.""",
                    }
                ],
            },
        ]
    else:
        messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": DAMN_SHORTEN_PROMPT_CLAUDE_NEW}],
            },
            {
                "role": "assistant",
                "content": [{"type": "text", "text": "Yes, I understand."}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""\n<Query>\n\n{prompt}\n</Query>\n\nAlso explain how you are following the Company Prompts Construction Guidelines and the Company Naming Conventions.""",
                    }
                ],
            },
        ]

    messages = [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": "You are an intelligent assistant who is an expert in extracting companies according to the instructions. He reads all the instructions thoroughly, then reads the whole query and then follows the instructions.",
                }
            ],
        }
    ] + messages

    # Set up retry mechanism for robustness
    MAX_RETRIES = 3
    retries = 0

    # Attempt to get a response from the LLM with retries
    while retries < MAX_RETRIES:
        try:
            # Call the LLM with the prepared messages
            response = await invoke(
                messages=messages,
                temperature=0,
                model="anthropic/claude-sonnet-4-latest",
                fallbacks=["openai/gpt-4.1"],
            )

            # Extract the output section from the response
            parsed_response = extract_generic("<Output>", "</Output>", response)
            text = eval(parsed_response.strip())

            # Process the response based on which prompts were generated
            # Case 1: No prompts generated
            if (
                not text.get("current_prompt")
                and not text.get("past_prompt")
                and not text.get("either_prompt")
            ):
                return {"current": None, "past": None, "timeline": None}
            # Case 2: Only current prompt generated
            elif text.get("current_prompt") and not text.get("past_prompt"):
                if not text.get("either_prompt"):
                    return {
                        "current": text.get("current_prompt"),
                        "past": None,
                        "timeline": "CURRENT",
                    }
                else:
                    return {
                        "current": text.get("current_prompt"),
                        "past": text.get("either_prompt"),
                        "timeline": "AND",
                    }
            # Case 3: Only past prompt generated
            elif text.get("past_prompt") and not text.get("current_prompt"):
                if not text.get("either_prompt"):
                    return {
                        "past": text.get("past_prompt"),
                        "current": None,
                        "timeline": "PAST",
                    }
                else:
                    return {
                        "past": text.get("past_prompt"),
                        "current": text.get("either_prompt"),
                        "timeline": "AND",
                    }
            # Case 4: Both current and past prompts generated
            elif text.get("past_prompt") and text.get("current_prompt"):
                return {
                    "past": text.get("past_prompt"),
                    "current": text.get("current_prompt"),
                    "timeline": "AND",
                }
            # Case 5: Only either prompt generated
            elif text.get("either_prompt"):
                return {
                    "past": None,
                    "current": text.get("either_prompt"),
                    "timeline": "OR",
                }

        except Exception as e:
            # Log the error and retry if possible
            print(e)
            traceback.print_exc()
            retries += 1

    # Return default values if all retries fail
    return {"current": None, "past": None, "timeline": None}
