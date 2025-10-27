from app.utils.search.aisearch.company.generation.prompts import (
    GENERATE_MORE_PROMPT_REFINE_SYSTEM_PROMPT,
)
from qutils.llm.asynchronous import invoke


async def generate_more_prompt_refine(prompt, companies):
    messages = [
        {"role": "system", "content": GENERATE_MORE_PROMPT_REFINE_SYSTEM_PROMPT},
        {"role": "user", "content": f"Prompt:{prompt}\nCompany Names: {companies}"},
    ]

    response = await invoke(
        messages=messages,
        model="openai/gpt-4.1",
        temperature=0.1,
        fallbacks=["anthropic/claude-3-5-haiku-latest"],
    )
    return response
