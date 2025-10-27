import json
import asyncio
import traceback
from app.utils.search.aisearch.company.generation.context import RequestContext
from app.utils.search.aisearch.company.generation.mapping import map_company
from app.utils.search.aisearch.company.generation.elastic import (
    get_company_source,
)
from app.utils.search.aisearch.company.generation.agents import (
    company_exclusion_agent,
    generate_companies_websearch,
    generate_obscure_companies,
    generate_more_companies,
    paraphrasing_agent,
)
from app.utils.search.aisearch.company.generation.models import (
    generate_companies,
    generate_companies_by_cognito,
)


async def check_task_completion(state: RequestContext, task_type: str):
    """
    Waits for a specific task to complete and returns its result.

    Args:
        state (RequestContext): Request context containing tasks
        task_type (str): The type of task to check

    Returns:
        The result of the completed task
    """
    return await state.wait_for_task(task_type)


async def process_companies(
    company_name,
    company_prompt,
    client,
    state: RequestContext,
    exclusion_flag=False,
    industries=None,
    score=1,
    esIds=[],
    output_type="CURRENT",
    mysql_pool=None,
    redis_client=None,
    product_filter=False,
):
    """
    Processes a company line and retrieves its data from various sources.

    This function processes a line containing company information, checks if it should be excluded,
    and retrieves the company's data from Elasticsearch or LinkedIn.

    Args:
        company_name (str): The company name to process
        company_prompt (str): The company prompt
        client: The Elasticsearch client
        state (RequestContext): Request context for managing state
        exclusion_flag (bool, optional): Whether to check for exclusion, defaults to False
        industries (list, optional): List of industries to filter by, defaults to None
        score (int, optional): Relevance score, defaults to 1
        esIds (list, optional): List of Elasticsearch IDs to exclude, defaults to empty list
        output_type (str, optional): The type of output, defaults to "CURRENT"
        mysql_pool: MySQL connection pool
        redis_client: Redis client
        product_filter (bool, optional): Whether to apply product filtering, defaults to False

    Returns:
        str: A JSON string containing the company data or None if not found
    """

    if 17 <= score <= 20:
        score = score - 16

    company_name = company_name.strip()
    if not company_name:
        return

    if not await state.add_company(company_name):
        return

    locations = None
    try:
        location_task = await state.get_task("LOCATION_MAPPING")
        if location_task:
            raw_locations = await asyncio.wait_for(
                check_task_completion(state, "LOCATION_MAPPING"), timeout=30.0
            )
            if isinstance(raw_locations, dict) and "location" in raw_locations:
                locations = raw_locations
            elif raw_locations:
                print(
                    f"Warning: LOCATION_MAPPING task returned unexpected format: {type(raw_locations)}"
                )
    except asyncio.TimeoutError:
        print(
            "Warning: LOCATION_MAPPING task timed out, continuing without location filtering"
        )
    except KeyError:
        pass
    except Exception as e:
        print(f"Warning: Failed to retrieve LOCATION_MAPPING data: {e}")

    if exclusion_flag:
        name_exclusion = await asyncio.gather(
            *[
                company_exclusion_agent(company_prompt, company_name),
                map_company(
                    company_name,
                    company_prompt,
                    industries,
                    client,
                    mysql_pool,
                    redis_client,
                    locations=locations,
                ),
            ]
        )
        exclusion = name_exclusion[0]
        es_id, source = name_exclusion[1]
    else:
        exclusion = False
        try:
            es_id, source = await map_company(
                company_name,
                company_prompt,
                industries,
                client,
                mysql_pool,
                redis_client,
                locations=locations,
            )
        except Exception as e:
            traceback.print_exc()
            print(e)
            return

    if es_id and source:
        response = await get_company_source(es_id, source)
        if response and (response["es_id"] not in esIds):
            data = {
                "es_data": response,
                "list": company_name,
                "excluded": exclusion,
                "type": output_type,
                "score": score,
            }
            if product_filter:
                data["es_source"] = source
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    else:
        return


async def process_stream(
    prompt,
    es_client,
    context=None,
    output_type="CURRENT",
    state: RequestContext = None,
    mysql_pool=None,
    redis_client=None,
    use_websearch=False,
    paraphrasing=False,
    product_filter=False,
    reasoning=True,
):
    """
    Processes a stream of company data based on the user's query.

    This function processes a stream of company data, either from a context or by generating
    new companies based on the user's query. It manages background tasks and timeouts
    to ensure efficient processing.

    Args:
        prompt (str): The system prompt
        es_client: The Elasticsearch client
        context (list, optional): List of existing companies, defaults to None
        output_type (str, optional): The type of output, defaults to "CURRENT"
        state (RequestContext): Request context for managing state
        mysql_pool: MySQL connection pool
        redis_client: Redis client
        use_websearch (bool, optional): Whether to use web search for company generation, defaults to False
        paraphrasing (bool, optional): Whether to paraphrase the prompt, defaults to False
        product_filter (bool, optional): Whether to apply product filtering, defaults to False
        reasoning (bool, optional): Whether to enable reasoning in company generation, defaults to True

    Yields:
        str: JSON strings containing company data
    """

    if paraphrasing:
        prompt = await paraphrasing_agent(prompt)

    line = ""
    background_tasks = []
    flag = False

    POOLING_CUTOFF = 50
    MAX_BACKGROUND_TASKS = 10
    MAX_TASK_TIMEOUT = 20.0
    MIN_TASK_TIMEOUT = 10.0
    TIMEOUT_DECREMENT = 0.1

    current_timeout = MAX_TASK_TIMEOUT

    async def prepare_for_processing():
        garbage = await check_task_completion(state, "GARBAGE")
        if garbage:
            return True, None, None

        exclusion_flag, industries = await asyncio.gather(
            check_task_completion(state, "EXCLUSION"),
            check_task_completion(state, "INDUSTRIES"),
        )
        return False, exclusion_flag, industries

    async def run_with_timeout(coroutine):
        nonlocal current_timeout
        try:
            return await asyncio.wait_for(coroutine, timeout=current_timeout)
        except asyncio.TimeoutError:
            return None

    async def check_completed_tasks():
        nonlocal current_timeout
        for task in list(background_tasks):
            if task.done():
                background_tasks.remove(task)
                current_timeout = max(
                    current_timeout - TIMEOUT_DECREMENT, MIN_TASK_TIMEOUT
                )
                try:
                    response = task.result()
                    if isinstance(response, list):
                        for res in response:
                            yield res
                    elif isinstance(response, str):
                        yield response
                except Exception as e:
                    print(f"Error in task: {e}")
                    yield f"Error in task: {str(e)}"

    async def wait_for_task_slot():
        """
        Efficiently waits for a slot to become available in the background tasks list
        and yields results from completed tasks.
        """
        nonlocal current_timeout
        while len(background_tasks) >= MAX_BACKGROUND_TASKS:
            done, pending = await asyncio.wait(
                background_tasks, return_when=asyncio.FIRST_COMPLETED
            )

            background_tasks[:] = list(pending)

            for task in done:
                current_timeout = max(
                    current_timeout - TIMEOUT_DECREMENT, MIN_TASK_TIMEOUT
                )
                try:
                    response = task.result()
                    if isinstance(response, list):
                        for res in response:
                            yield res
                    elif isinstance(response, str):
                        yield response
                except Exception as e:
                    print(f"Error in task: {e}")

    if use_websearch:

        async def process_generator(generator):
            nonlocal line, flag, POOLING_CUTOFF
            line = ""
            flag = False
            company_names = []

            async for result in generator:
                line += result
                if "<companies>" in line.lower():
                    flag = True
                    line = ""

                if flag and ("\n" in result):
                    line = line.strip()
                    (
                        is_garbage,
                        exclusion_flag,
                        industries,
                    ) = await prepare_for_processing()
                    if is_garbage:
                        return

                    async for result in wait_for_task_slot():
                        yield result

                    company_names.append(line)
                    task = asyncio.create_task(
                        run_with_timeout(
                            process_companies(
                                line,
                                prompt,
                                es_client,
                                state,
                                exclusion_flag,
                                industries,
                                output_type=output_type,
                                mysql_pool=mysql_pool,
                                redis_client=redis_client,
                                product_filter=product_filter,
                            )
                        )
                    )
                    background_tasks.append(task)
                    line = ""
                    POOLING_CUTOFF += 1

                    async for result in check_completed_tasks():
                        yield result

        async for result in process_generator(generate_companies_websearch(prompt)):
            yield result

    else:
        if context:
            es_ids = [item["es_id"] for item in context]
            unique_es_ids = list(set(es_ids))

            async def process_context_generator(generator):
                nonlocal line, flag, POOLING_CUTOFF
                async for result in generator:
                    line += result
                    if "<companies>" in line.lower():
                        flag = True
                        line = ""

                    if flag and ("\n" in result):
                        line = line.strip()
                        (
                            is_garbage,
                            exclusion_flag,
                            industries,
                        ) = await prepare_for_processing()
                        if is_garbage:
                            return

                        async for result in wait_for_task_slot():
                            yield result

                        task = asyncio.create_task(
                            run_with_timeout(
                                process_companies(
                                    line,
                                    prompt,
                                    es_client,
                                    state,
                                    exclusion_flag,
                                    industries,
                                    esIds=unique_es_ids,
                                    output_type=output_type,
                                    mysql_pool=mysql_pool,
                                    redis_client=redis_client,
                                    product_filter=product_filter,
                                )
                            )
                        )
                        background_tasks.append(task)
                        line = ""
                        POOLING_CUTOFF += 1

                        async for result in check_completed_tasks():
                            yield result

            async for result in process_context_generator(
                generate_more_companies(prompt, context)
            ):
                yield result

            if line and "<" not in line and ">" not in line:
                try:
                    (is_garbage, exclusion_flag, industries) = (
                        await prepare_for_processing()
                    )
                    if is_garbage:
                        return

                    async for result in wait_for_task_slot():
                        yield result

                    task = asyncio.create_task(
                        run_with_timeout(
                            process_companies(
                                line,
                                prompt,
                                es_client,
                                state,
                                exclusion_flag,
                                industries,
                                esIds=unique_es_ids,
                                output_type=output_type,
                                mysql_pool=mysql_pool,
                                redis_client=redis_client,
                                product_filter=product_filter,
                            )
                        )
                    )
                    background_tasks.append(task)
                    POOLING_CUTOFF += 1

                    async for result in check_completed_tasks():
                        yield result

                except Exception as e:
                    print("Error in generating last company: ", e)

        else:
            fame = await check_task_completion(state, "FAME")

            async def process_generator(generator):
                nonlocal line, flag, POOLING_CUTOFF
                line = ""
                flag = False
                company_names = []

                async for result in generator:
                    if not isinstance(line, str):
                        line = ""
                    if isinstance(result, str):
                        line += result

                    if "<companies>" in line.lower():
                        flag = True
                        line = ""

                    if flag and ("\n" in result):
                        line = line.strip()
                        if not line:
                            line = ""
                            continue

                        company = line
                        score = 1

                        if "~" in line:
                            parts = line.split("~")
                            if len(parts) >= 2:
                                company = parts[0].strip()
                                score_str = parts[1].strip()
                                try:
                                    parsed_score = int(score_str)
                                    score = parsed_score
                                except (ValueError, TypeError):
                                    line = ""
                                    continue
                            else:
                                line = ""
                                continue

                        if not company:
                            line = ""
                            continue

                        (is_garbage, exclusion_flag, industries) = (
                            await prepare_for_processing()
                        )
                        if is_garbage:
                            return

                        async for result in wait_for_task_slot():
                            yield result

                        company_names.append(company)
                        task = asyncio.create_task(
                            run_with_timeout(
                                process_companies(
                                    company,
                                    prompt,
                                    es_client,
                                    state,
                                    exclusion_flag,
                                    industries,
                                    score=score,
                                    output_type=output_type,
                                    mysql_pool=mysql_pool,
                                    redis_client=redis_client,
                                    product_filter=product_filter,
                                )
                            )
                        )
                        background_tasks.append(task)
                        line = ""
                        POOLING_CUTOFF += 1

                        async for result in check_completed_tasks():
                            yield result

            if fame not in ["missing", "famous"]:
                try:
                    industries = await check_task_completion(state, "INDUSTRIES")

                    locations = None
                    try:
                        location_task = await state.get_task("LOCATION_MAPPING")
                        if location_task:
                            raw_locations = await asyncio.wait_for(
                                check_task_completion(state, "LOCATION_MAPPING"),
                                timeout=30.0,
                            )
                            if (
                                isinstance(raw_locations, dict)
                                and "location" in raw_locations
                            ):
                                locations = raw_locations
                    except (asyncio.TimeoutError, KeyError):
                        pass

                    _, es_data = await map_company(
                        fame,
                        prompt,
                        industries,
                        es_client,
                        mysql_pool,
                        redis_client,
                        locations=locations,
                    )

                    if es_data:
                        async for result in process_generator(
                            generate_obscure_companies(prompt, es_data)
                        ):
                            yield result
                    else:
                        raise Exception()
                except:
                    async for result in process_generator(
                        generate_companies_by_cognito(prompt, reasoning=reasoning)
                    ):
                        yield result
            else:
                async for result in process_generator(
                    generate_companies_by_cognito(prompt, reasoning=reasoning)
                ):
                    yield result

    tasks_to_process = set(background_tasks)
    if tasks_to_process:
        while tasks_to_process and POOLING_CUTOFF > 0:
            done, pending = await asyncio.wait(
                tasks_to_process, return_when=asyncio.FIRST_COMPLETED
            )
            tasks_to_process = pending

            for task in done:
                try:
                    response = task.result()
                    current_timeout = max(
                        current_timeout - TIMEOUT_DECREMENT, MIN_TASK_TIMEOUT
                    )
                    if isinstance(response, list):
                        for res in response:
                            yield res
                    elif isinstance(response, str):
                        yield response
                except Exception as e:
                    print(f"Error in task: {e}")
                    yield f"Error in task: {str(e)}"

            POOLING_CUTOFF -= 1
