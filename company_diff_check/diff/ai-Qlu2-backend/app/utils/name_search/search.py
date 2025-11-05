import re
from qutils.llm.asynchronous import invoke
from app.utils.name_search.prompts import NAME_SEARCH_SYSTEM_PROMPT


def extract_generic(start: str, end: str, text: str):
    match = re.search(rf"{start}(.*?){end}", text, re.DOTALL)
    return match.group(1) if match else None


async def grok(messages, model="llama-3.3-70b-versatile", check=True):
    retries = 3
    for i in range(retries):
        try:

            response = await invoke(
                messages=messages,
                temperature=0.1,
                model="groq/" + model,
                fallbacks=["openai/gpt-4.1"],
            )
            response = re.sub(
                r"\b(null|false|true)\b",
                lambda m: {"null": "None", "false": "False", "true": "True"}[
                    m.group(0)
                ],
                response,
            )

            response = extract_generic("<Output>", "</Output>", response)
            final_response = eval(response)

            return final_response
        except Exception as e:
            raise e

    return {}


async def main(query):
    messages = [
        {"role": "system", "content": NAME_SEARCH_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"**Now, process the following searchString:**\n: {query}",
        },
    ]

    result = await grok(messages)
    if not result.get("people", None):
        result["people"] = []
    return result
