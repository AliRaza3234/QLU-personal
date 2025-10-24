import re
import ast
import json
import asyncio
from app.utils.search.aisearch.company.generation.prompts import (
    EXCLUSION_CHECKING_SYSTEM_PROMPT,
    EXTRACT_INDUSTRY_KEYWORDS_SYSTEM_PROMPT,
    FAME_CHECKER_SYSTEM_PROMPT,
    FAME_CHECKER_USER_PROMPT,
    GARBAGE_DETECTOR_SYSTEM_PROMPT,
    GARBAGE_DETECTOR_USER_PROMPT,
    LOCATION_SYSTEM_PROMPT,
    LOCATION_USER_PROMPT,
    SIZE_SYSTEM_PROMPT,
    SIZE_USER_PROMPT,
    EXCLUSION_COMPANY_CLASSIFIER_USER_PROMPT,
    EXCLUSION_COMPANY_CLASSIFIER_SYSTEM_PROMPT,
    GENERATE_OBSCURE_COMPANIES_USER_PROMPT,
    GENERATE_OBSCURE_COMPANIES_SYSTEM_PROMPT,
    GENERATE_MORE_COMPANIES_USER_PROMPT,
    GENERATE_MORE_COMPANIES_SYSTEM_PROMPT,
    STANDARD_COMPANY_INDUSTRIES,
    GENERATION_SYSTEM_PROMPT,
    OE_DETECTOR_SYSTEM_PROMPT,
    L_DETECTOR_SYSTEM_PROMPT,
    L_DETECTOR_SYSTEM_PROMPT_2,
    PARAPHRASING_PROMPT,
    GENERATION_SYSTEM_PROMPT_NON_REASONING,
)
from app.utils.search.aisearch.company.generation.utilities import (
    post_process_gpt_output,
    ownership_checker,
)

from qutils.llm.agents.industry import breakdown
from qutils.llm.asynchronous import invoke, stream


async def garbage_detecting_agent(userquery, current_prompt, past_prompt):
    """
    Determines if a user prompt is nonsensical or contains garbage content.

    This agent analyzes the user's prompt to determine if it contains meaningful
    content or if it's nonsensical/garbage that should be filtered out.

    Args:
        prompt (str): The user's input prompt to analyze

    Returns:
        bool: True if the prompt is garbage/nonsensical, False otherwise

    Raises:
        Exception: If all retry attempts fail
    """
    retries = 3

    if len(current_prompt) > len(past_prompt):
        prompt = current_prompt
    else:
        prompt = past_prompt

    if userquery == prompt:
        final_prompt = f"""
        Company Prompt: {prompt}
        """
    else:
        final_prompt = f"""
        User Prompt: {userquery}
        Company Prompt: {prompt}
        """

    for attempt in range(retries + 1):
        try:
            # Format the user prompt with the template
            user_prompt = (
                GARBAGE_DETECTOR_USER_PROMPT
                + f"""
            <prompt>
                {final_prompt}
            </prompt>    
            """
            )

            # Call the LLM with the formatted prompt
            response = await invoke(
                messages=[
                    {"role": "system", "content": GARBAGE_DETECTOR_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                model="groq/llama-3.3-70b-versatile",
                temperature=0,
                fallbacks=["openai/gpt-4.1"],
            )

            # Extract the response and determine if it's garbage
            response = response.split("<Output>")[1].split("</Output>")[0].strip()
            if response == "garbage":
                return True
            return False
        except Exception as e:
            # Implement exponential backoff for retries
            if attempt < retries:
                wait_time = 2**attempt
                print(
                    f"Attempt {attempt + 1} failed for garbage_detecting_agent: {str(e)}. Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)
            else:
                print(
                    f"All {retries} retry attempts failed for garbage_detecting_agent: {str(e)}"
                )
                raise


async def location_detection(prompt):
    """
    Detects if a user prompt contains location-specific information.

    This agent analyzes the user's prompt to determine if it contains
    information about a specific location or geographic area.

    Args:
        prompt (str): The user's input prompt to analyze

    Returns:
        bool: True if the prompt contains location information, False otherwise

    Raises:
        Exception: If all retry attempts fail
    """
    retries = 3

    for attempt in range(retries + 1):
        try:
            # Format the user prompt with the template
            user_prompt = (
                LOCATION_USER_PROMPT
                + f"""
                <Sentence>
                    {prompt}
                </Sentence>
            """
            )

            # Call the LLM with the formatted prompt
            response = await invoke(
                messages=[
                    {"role": "system", "content": LOCATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                model="groq/llama-3.3-70b-versatile",
                temperature=0,
                fallbacks=["openai/gpt-4.1"],
            )

            # Process the response and determine if it contains location information
            response = post_process_gpt_output(response)
            if "true" in response.lower():
                return True
            return False
        except Exception as e:
            # Implement exponential backoff for retries
            if attempt < retries:
                wait_time = 2**attempt
                print(
                    f"Attempt {attempt + 1} failed for location_detection: {str(e)}. Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)
            else:
                print(
                    f"All {retries} retry attempts failed for location_detection: {str(e)}"
                )
                raise


def extract_json(text):
    match = re.search(r"```json\n({.*?})\n```", text, re.DOTALL)
    if match:
        return match.group(1)
    return None


async def detect_ownership_and_employee_count(current_prompt, past_prompt, es_client):
    retries = 3
    prompt = current_prompt if len(current_prompt) > len(past_prompt) else past_prompt

    for attempt in range(retries + 1):
        try:
            response = await invoke(
                messages=[
                    {"role": "system", "content": OE_DETECTOR_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                model="openai/gpt-4.1",
                fallbacks=["anthropic/claude-sonnet-4-latest"],
            )

            # Try parsing the response as JSON
            try:
                response_json = json.loads(
                    response[response.find("{") : response.rfind("}") + 1]
                )
            except Exception:
                try:
                    response_json = json.loads(extract_json(response))
                except Exception:
                    response_json = ast.literal_eval(
                        response[
                            response[: response.rfind("{")].rfind("{") : response.rfind(
                                "}"
                            )
                            + 1
                        ]
                    )

            upper_range = response_json["employee_count"]["upper"]
            lower_range = response_json["employee_count"]["lower"]
            ownership_status = response_json["ownership_status"]
            if ownership_status:
                ownership_data = await ownership_checker(ownership_status, es_client)
            else:
                ownership_data = []

            return lower_range, upper_range, ownership_status, ownership_data

        except Exception as e:
            if attempt < retries:
                wait_time = 2**attempt
                print(
                    f"Attempt {attempt + 1} failed for detect_ownership_and_employee_count: {str(e)}. Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)
            else:
                print(
                    f"All {retries} retry attempts failed for detect_ownership_and_employee_count: {str(e)}"
                )
                raise


async def detect_country_state_city(current_prompt, past_prompt):
    retries = 3
    prompt = current_prompt if len(current_prompt) > len(past_prompt) else past_prompt

    for attempt in range(retries + 1):
        try:
            response = await invoke(
                messages=[
                    {"role": "system", "content": L_DETECTOR_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                model="openai/gpt-4.1",
                fallbacks=["anthropic/claude-sonnet-4-latest"],
            )

            try:
                response_json = json.loads(
                    response[response.find("{") : response.rfind("}") + 1]
                )
            except Exception:
                try:
                    response_json = json.loads(extract_json(response))
                except Exception:
                    response_json = ast.literal_eval(
                        response[
                            response[: response.rfind("{")].rfind("{") : response.rfind(
                                "}"
                            )
                            + 1
                        ]
                    )

            return response_json

        except Exception as e:
            if attempt < retries:
                wait_time = 2**attempt
                print(
                    f"Attempt {attempt + 1} failed for detect_country_state_city: {str(e)}. Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)
            else:
                print(
                    f"All {retries} retry attempts failed for detect_country_state_city: {str(e)}"
                )
                raise


async def detect_location_for_mapping(current_prompt, past_prompt):
    """
    Detects location information for company mapping using GPT-OSS-120B with reasoning.
    Uses L_DETECTOR_SYSTEM_PROMPT_2 which always infers country even if not explicitly mentioned.

    Args:
        current_prompt (str): The current search prompt
        past_prompt (str): The previous search prompt

    Returns:
        dict: Location data in format {"location": [{"country": "", "state": "", "city": ""}]}
    """
    retries = 3
    prompt = current_prompt if len(current_prompt) > len(past_prompt) else past_prompt

    for attempt in range(retries + 1):
        try:
            response = await invoke(
                messages=[
                    {"role": "system", "content": L_DETECTOR_SYSTEM_PROMPT_2},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                top_p=1,
                model="groq/openai/gpt-oss-120b",
                reasoning_effort="medium",
                fallbacks=["groq/openai/gpt-oss-20b"],
            )

            # Extract content from response (handles both direct string and choices format)
            if hasattr(response, "choices"):
                response_content = response.choices[0].message.content
            else:
                response_content = response

            try:
                response_json = json.loads(
                    response_content[
                        response_content.find("{") : response_content.rfind("}") + 1
                    ]
                )
            except Exception:
                try:
                    response_json = json.loads(extract_json(response_content))
                except Exception:
                    response_json = ast.literal_eval(
                        response_content[
                            response_content[: response_content.rfind("{")].rfind(
                                "{"
                            ) : response_content.rfind("}")
                            + 1
                        ]
                    )
            return response_json

        except Exception as e:
            if attempt < retries:
                wait_time = 2**attempt
                print(
                    f"Attempt {attempt + 1} failed for detect_location_for_mapping: {str(e)}. Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)
            else:
                print(
                    f"All {retries} retry attempts failed for detect_location_for_mapping: {str(e)}"
                )
                raise


async def extract_industry_keywords(current_prompt: str, past_prompt: str):
    """
    Extracts industry keywords from a user prompt.
    Also returns a list of industry synonyms for each industry keyword.

    This function analyzes the user's prompt to identify and extract industry keywords.
    It returns a list of industry keywords found in the prompt.

    Args:
        prompt (str): The user's input prompt to analyze
    """

    if len(current_prompt) > len(past_prompt):
        prompt = current_prompt
    else:
        prompt = past_prompt

    response = await asyncio.gather(
        *[
            breakdown(prompt, num_industries=10),
            invoke(
                messages=[
                    {
                        "role": "system",
                        "content": EXTRACT_INDUSTRY_KEYWORDS_SYSTEM_PROMPT,
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                model="anthropic/claude-sonnet-4-latest",
                fallbacks=["openai/gpt-4.1"],
            ),
        ]
    )
    industry_keywords = response[0]
    special_requirements = response[1]

    special_requirements = json.loads(
        special_requirements[
            special_requirements.find("{") : special_requirements.rfind("}") + 1
        ]
    )
    if not special_requirements:
        return None
    return special_requirements, industry_keywords


async def size_estimator(prompt):
    """
    Estimates the size range of companies mentioned in a user prompt.

    This agent analyzes the user's prompt to determine the size range
    of companies that should be included in the results.

    Args:
        prompt (str): The user's input prompt to analyze

    Returns:
        str: The estimated company size range (e.g., "10~100")

    Raises:
        Exception: If all retry attempts fail
    """
    retries = 3

    for attempt in range(retries + 1):
        try:
            # Format the user prompt with the template
            user_prompt = (
                SIZE_USER_PROMPT
                + f"""
                <User-Prompt>
                    {prompt}
                </User-Prompt>
            """
            )

            # Call the LLM with the formatted prompt
            response = await invoke(
                messages=[
                    {"role": "system", "content": SIZE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
                model="groq/llama-3.3-70b-versatile",
                fallbacks=["openai/gpt-4.1"],
            )

            # Process and return the response
            response = post_process_gpt_output(response)
            return response
        except Exception as e:
            # Implement exponential backoff for retries
            if attempt < retries:
                wait_time = 2**attempt
                print(
                    f"Attempt {attempt + 1} failed for size_estimator: {str(e)}. Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)
            else:
                print(
                    f"All {retries} retry attempts failed for size_estimator: {str(e)}"
                )
                raise


async def exclusion_checking_agent(current_prompt, past_prompt):
    """
    Determines if a user prompt should be excluded from processing.

    This agent analyzes the user's prompt to determine if it contains
    content that should be excluded from further processing.

    Args:
        prompt (str): The user's input prompt to analyze

    Returns:
        bool: True if the prompt should be excluded, False otherwise

    Raises:
        Exception: If all retry attempts fail
    """
    retries = 3

    if len(current_prompt) > len(past_prompt):
        prompt = current_prompt
    else:
        prompt = past_prompt

    for attempt in range(retries + 1):
        try:
            response = await invoke(
                messages=[
                    {"role": "system", "content": EXCLUSION_CHECKING_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                model="groq/llama-3.3-70b-versatile",
                fallbacks=["openai/gpt-4.1"],
            )

            # Process the response and determine if it should be excluded
            response = post_process_gpt_output(response)
            if response == "exclude":
                return True
            return False
        except Exception as e:
            # Implement exponential backoff for retries
            if attempt < retries:
                wait_time = 2**attempt
                print(
                    f"Attempt {attempt + 1} failed for exclusion_checking_agent: {str(e)}. Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)
            else:
                print(
                    f"All {retries} retry attempts failed for exclusion_checking_agent: {str(e)}"
                )
                raise


async def fame_checker(prompt):
    """
    Determines the fame level of companies mentioned in a user prompt.

    This agent analyzes the user's prompt to determine the fame level
    of companies that should be included in the results.

    Args:
        prompt (str): The user's input prompt to analyze

    Returns:
        str: The fame level of companies (e.g., "famous", "obscure", "mixed")

    Raises:
        Exception: If all retry attempts fail
    """
    retries = 3

    for attempt in range(retries + 1):
        try:
            # Format the user prompt with the template
            user_prompt = (
                FAME_CHECKER_USER_PROMPT
                + f"""
            <prompt>
                {prompt}
            </prompt>    
            """
            )

            # Call the LLM with the formatted prompt
            response = await invoke(
                messages=[
                    {"role": "system", "content": FAME_CHECKER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
                model="groq/llama-3.3-70b-versatile",
                fallbacks=["openai/gpt-4.1"],
            )

            return response
        except Exception as e:
            # Implement exponential backoff for retries
            if attempt < retries:
                wait_time = 2**attempt
                print(
                    f"Attempt {attempt + 1} failed for fame_checker: {str(e)}. Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)
            else:
                print(f"All {retries} retry attempts failed for fame_checker: {str(e)}")
                raise


async def company_exclusion_agent(prompt, company):
    """
    Determines if a specific company should be excluded from results.

    This agent analyzes a company name in the context of a user prompt
    to determine if it should be excluded from the results.

    Args:
        prompt (str): The user's input prompt
        company (str): The name of the company to check

    Returns:
        bool: True if the company should be excluded, False otherwise
    """
    # Format the user prompt with the template
    user_prompt = (
        EXCLUSION_COMPANY_CLASSIFIER_USER_PROMPT
        + f"""
    <prompt>
        {prompt}
    </prompt>
    <company>
        {company}
    </company>
    """
    )

    # Call the LLM with the formatted prompt
    response = await invoke(
        messages=[
            {"role": "system", "content": EXCLUSION_COMPANY_CLASSIFIER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        model="groq/llama-3.3-70b-versatile",
        fallbacks=["openai/gpt-4.1"],
    )

    # Process the response and determine if the company should be excluded
    response = post_process_gpt_output(response)
    if "exclude" in response.lower():
        return True
    return False


async def generate_companies(prompt, reasoning=False):
    """
    Generates a list of companies based on the user prompt and size criteria.
    This agent generates a list of companies that match the user's prompt and the specified company size range.
    Args:
        prompt (str): The user's input prompt
        reasoning (bool): Whether to use reasoning in generation, defaults to False
    Yields:
        str: Chunks of the generated company list
    """
    if reasoning:
        system_prompt = GENERATION_SYSTEM_PROMPT
    else:
        system_prompt = GENERATION_SYSTEM_PROMPT_NON_REASONING

    primary_model = "openai/gpt-4.1"
    fallback_model = "groq/moonshotai/kimi-k2-instruct"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    primary_stream = stream(
        messages=messages,
        temperature=0.4,
        top_p=0.7,
        model=primary_model,
    )

    line_count = 0

    try:
        first_chunk = await asyncio.wait_for(anext(primary_stream), timeout=5.0)
        yield first_chunk

        if not reasoning and "\n" in first_chunk:
            line_count = first_chunk.count("\n")
            if line_count > 5:
                return

        async for chunk in primary_stream:
            if not reasoning and "\n" in chunk:
                line_count += chunk.count("\n")
                if line_count > 5:
                    yield chunk
                    return
            yield chunk

    except (asyncio.TimeoutError, StopAsyncIteration):
        try:
            await primary_stream.aclose()
        except AttributeError:
            pass

        line_count = 0
        async for chunk in stream(
            messages=messages,
            temperature=0.4,
            top_p=0.7,
            model=fallback_model,
        ):
            if not reasoning and "\n" in chunk:
                line_count += chunk.count("\n")
                if line_count > 5:
                    yield chunk
                    return
            yield chunk


async def generate_companies_websearch(prompt):
    async for chunk in stream(
        messages=[
            {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": prompt
                + "\nPerform websearch. Follow output format from the system prompt. Make sure you generate company names that exist on LinkedIn.",
            },
        ],
        model="openai/gpt-4o-search-preview",
    ):
        yield chunk


async def generate_obscure_companies(prompt, added_info):
    """
    Generates a list of obscure companies based on the user prompt and additional information.

    This agent generates a list of obscure companies that match the user's prompt
    and the provided additional information.

    Args:
        prompt (str): The user's input prompt
        added_info (dict): Additional information to guide company generation

    Yields:
        str: Chunks of the generated company list
    """
    user_prompt = (
        GENERATE_OBSCURE_COMPANIES_USER_PROMPT
        + f"""
        <Prompt>
        {prompt}
        </Prompt>
        <Additional Information>
        {json.dumps(added_info)}
        </Additional Information>
    """
    )

    messages = [
        {"role": "system", "content": GENERATE_OBSCURE_COMPANIES_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    primary_model = "openai/gpt-4.1"
    fallback_model = "groq/moonshotai/kimi-k2-instruct"

    primary_stream = stream(
        messages=messages,
        temperature=0,
        model=primary_model,
    )

    try:
        first_chunk = await asyncio.wait_for(anext(primary_stream), timeout=5.0)
        yield first_chunk

        async for chunk in primary_stream:
            yield chunk

    except (asyncio.TimeoutError, StopAsyncIteration):
        try:
            await primary_stream.aclose()
        except AttributeError:
            pass

        async for chunk in stream(
            messages=messages,
            temperature=0,
            model=fallback_model,
        ):
            yield chunk


async def generate_more_companies(prompt, context):
    """
    Generates additional companies based on the user prompt and existing context.

    This agent generates more companies that match the user's prompt
    and are different from the companies already in the context.

    Args:
        prompt (str): The user's input prompt
        context (list): List of dictionaries containing company information

    Yields:
        str: Chunks of the generated company list
    """
    names = [item["name"] for item in context if item["is_selected"] == True]
    unselected_names = [
        item["name"] for item in context if item["is_selected"] == False
    ]

    user_prompt = (
        GENERATE_MORE_COMPANIES_USER_PROMPT
        + f"""
        <Prompt>
        {prompt}
        </Prompt>
        <Selected_Companies>
        {names}
        </Selected_Companies>
        <Unselected_Companies>
        {unselected_names}
        </Unselected_Companies>
    """
    )

    messages = [
        {"role": "system", "content": GENERATE_MORE_COMPANIES_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    primary_model = "openai/gpt-4.1"
    fallback_model = "groq/moonshotai/kimi-k2-instruct"

    primary_stream = stream(
        messages=messages,
        temperature=0,
        model=primary_model,
    )

    try:
        first_chunk = await asyncio.wait_for(anext(primary_stream), timeout=5.0)
        yield first_chunk

        async for chunk in primary_stream:
            yield chunk

    except (asyncio.TimeoutError, StopAsyncIteration):
        try:
            await primary_stream.aclose()
        except AttributeError:
            pass

        async for chunk in stream(
            messages=messages,
            temperature=0,
            model=fallback_model,
        ):
            yield chunk


async def company_industries(user_query):
    response = await invoke(
        messages=[
            {
                "role": "system",
                "content": STANDARD_COMPANY_INDUSTRIES,
            },
            {
                "role": "user",
                "content": f"""{user_query}
""",
            },
        ],
        model="groq/llama-3.3-70b-versatile",
        temperature=0,
        fallbacks=["openai/gpt-4.1"],
    )

    if "None" in response:
        return None
    return [
        i
        for i in [
            i.strip()
            for i in response.split("<industries>")[1]
            .split("</industries>")[0]
            .split("\n")
        ]
        if i
    ]


async def paraphrasing_agent(prompt):
    response = await invoke(
        messages=[
            {
                "role": "system",
                "content": PARAPHRASING_PROMPT,
            },
            {"role": "user", "content": prompt},
        ],
        model="anthropic/claude-sonnet-4-latest",
        temperature=0,
        fallbacks=["openai/gpt-4.1"],
    )
    return response
