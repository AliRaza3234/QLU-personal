from app.core.database import postgres_fetch
from qutils.llm.asynchronous import invoke


async def search_functional_area(universalname):
    query = f"""
                SELECT consolidated_f_a
                FROM consolidated_functional_areas
                WHERE universalname = '{universalname}';
            """
    result = await postgres_fetch(query)
    return result


async def get_functional_area(request):
    title = request.get("title", None)
    headline = request.get("headline", None)
    universal_name = request.get("universal_name", None)
    functional_areas = request.get("functional_areas", None)

    profile_data = ""
    if title:
        profile_data += f"Title: {title}"
    if headline:
        profile_data += f", Headline: {headline}"

    dynamic_functional_areas = None

    if functional_areas is None:
        if universal_name:
            dynamic_functional_areas = await search_functional_area(universal_name)
        else:
            dynamic_functional_areas = [functional_areas]
    else:
        dynamic_functional_areas = [functional_areas]

    functions = [
        "Sales",
        "Marketing",
        "Engineering",
        "Program Management",
        "Finance",
        "Operations",
        "Product Management",
        "Security",
        "Human Resources",
        "Legal",
        "Consulting",
        "Education",
        "Strategy",
        "Design",
        "Research",
        "Manufacturing",
        "Creative",
        "General Management",
        "Customer Success",
        "Business Development",
        "Information Technology",
        "Compliance",
        "Risk Management",
        "Business Intelligence",
    ]
    if dynamic_functional_areas:
        functional_areas = list(set(dynamic_functional_areas[0] + functions))
    else:
        functional_areas = functions

    functions_string = "\n".join(functional_areas)
    system_prompt = f"""
You are an intelligent assistant whose job is to determine the functional area of a person based on their data.
These functions are usually:
{functions_string}
If the input is jibberish and you can't make sense of any function return None

Important Note: You are only allowed to return the functional area in your output nothing else!
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Profile Data:\n{profile_data}"},
    ]

    response = await invoke(
        messages=messages,
        temperature=0,
        model="openai/gpt-4o-mini",
        fallbacks=["anthropic/claude-3-5-haiku-latest"],
    )

    if response in functional_areas:
        return response
    return None
