import json
import asyncio

from app.utils.search.aisearch.company.generation.context import RequestContext
from app.utils.search.aisearch.company.generation.agents import (
    exclusion_checking_agent,
    extract_industry_keywords,
    fame_checker,
    garbage_detecting_agent,
    company_industries,
    detect_ownership_and_employee_count,
    detect_country_state_city,
    detect_location_for_mapping,
)
from app.utils.search.aisearch.company.generation.industry import (
    get_companies_by_industry,
)
from app.utils.search.aisearch.company.generation.stream import (
    process_stream,
    check_task_completion,
)
from app.utils.search.aisearch.company.generation.utilities import (
    ownership_checker,
)


async def initialize_tasks(
    userquery,
    current_prompt,
    past_prompt,
    state: RequestContext,
    company_ownership,
    es_client,
):
    """
    Initialize and run multiple analysis tasks for a given user query.

    This function creates asynchronous tasks for various analysis agents that process
    the user query in parallel. Each task has a timeout retry mechanism to handle
    potential failures.

    Args:
        userquery (str): The user's search query to be analyzed
        current_prompt (str): The current search prompt
        past_prompt (str): The previous search prompt
        state (RequestContext): Request context for managing state
        company_ownership: Company ownership data
        es_client: Elasticsearch client

    Returns:
        None: Tasks are stored in the request context
    """

    async def run_with_timeout_retry(coro_func, *args, max_attempts=3, timeout=5):
        """
        Execute a coroutine with timeout and retry logic.

        Args:
            coro_func: The coroutine function to execute
            *args: Arguments to pass to the coroutine function
            max_attempts (int): Maximum number of retry attempts before giving up

        Returns:
            The result of the coroutine or None if all attempts fail
        """
        attempts = 0
        while attempts < max_attempts:
            try:
                coroutine = coro_func(*args)
                return await asyncio.wait_for(coroutine, timeout=timeout)
            except asyncio.TimeoutError:
                attempts += 1
                if attempts >= max_attempts:
                    return None

    tasks_dict = {
        "EXCLUSION": asyncio.create_task(
            run_with_timeout_retry(
                exclusion_checking_agent, current_prompt, past_prompt
            )
        ),
        "FAME": asyncio.create_task(run_with_timeout_retry(fame_checker, userquery)),
        "INDUSTRIES": asyncio.create_task(company_industries(userquery)),
        "GARBAGE": asyncio.create_task(
            run_with_timeout_retry(
                garbage_detecting_agent, userquery, current_prompt, past_prompt
            )
        ),
        "OWNERSHIP": asyncio.create_task(
            run_with_timeout_retry(ownership_checker, company_ownership, es_client)
        ),
        "PRUNING": asyncio.create_task(
            run_with_timeout_retry(
                detect_ownership_and_employee_count,
                current_prompt,
                past_prompt,
                es_client,
                timeout=15,
            )
        ),
        "LOCATION": asyncio.create_task(
            run_with_timeout_retry(
                detect_country_state_city, current_prompt, past_prompt, timeout=30
            )
        ),
        "LOCATION_MAPPING": asyncio.create_task(
            run_with_timeout_retry(
                detect_location_for_mapping, current_prompt, past_prompt, timeout=30
            )
        ),
        "KEYWORDS": asyncio.create_task(
            run_with_timeout_retry(
                extract_industry_keywords, current_prompt, past_prompt, timeout=15
            )
        ),
    }

    await state.set_tasks(tasks_dict)


async def generate(
    current_prompt,
    past_prompt,
    es_client,
    context=None,
    userquery="",
    employee_count={},
    company_ownership=[],
    mysql_pool=None,
    redis_client=None,
    product_filter=False,
):
    """
    Process company search using both current and past prompts simultaneously.

    This function implements a dual-strategy approach where both current and past prompts
    are processed in parallel, with results being interleaved in the output stream.
    It also initializes various analysis tasks for the user query.

    Args:
        current_prompt (str): The current search prompt
        past_prompt (str): The previous search prompt
        es_client: Elasticsearch client for data retrieval
        context (dict, optional): Additional context for the search
        userquery (str, optional): User's original query, defaults to empty string

    Yields:
        str: Processed responses from both current and past streams
    """

    current_prompt = current_prompt or ""
    past_prompt = past_prompt or ""

    lower_range = employee_count.get("lower_range", 0)
    upper_range = employee_count.get("upper_range", 9999999)

    iterator = 0
    if userquery == "":
        userquery = (
            current_prompt if current_prompt and not past_prompt else past_prompt
        )

    state = RequestContext()

    asyncio.create_task(
        initialize_tasks(
            userquery,
            current_prompt,
            past_prompt,
            state,
            company_ownership,
            es_client,
        )
    )

    async def stream_current(lower_range, upper_range, company_ownership):
        ownership_data = None
        current_universalnames = set()

        if not current_prompt:
            return

        queue = asyncio.Queue()

        async def consume_stream(paraphrasing, reasoning):
            nonlocal lower_range, upper_range, ownership_data
            async for response in process_stream(
                current_prompt,
                es_client,
                context,
                "CURRENT",
                state,
                mysql_pool,
                redis_client,
                use_websearch=False,
                paraphrasing=paraphrasing,
                product_filter=product_filter,
                reasoning=reasoning,
            ):
                text = str(response)
                if "data: {" not in text:
                    continue

                data = json.loads(text[text.find("{") : text.rfind("}") + 1])
                employee_count = data.get("es_data", {}).get("employCount", 0)
                universal_name = data.get("es_data", {}).get("universalName", "")

                if not employee_count or not universal_name:
                    continue

                if (
                    lower_range == 0 and upper_range == 9999999
                ) or company_ownership == []:
                    (
                        lower_employee_count,
                        upper_employee_count,
                        _,
                        company_ownership_data,
                    ) = await check_task_completion(state, "PRUNING")
                    if lower_range == 0 and upper_range == 9999999:
                        lower_range = lower_employee_count
                        upper_range = upper_employee_count
                    if company_ownership == []:
                        ownership_data = company_ownership_data

                if not ownership_data and company_ownership:
                    ownership_data = await check_task_completion(state, "OWNERSHIP")

                if not isinstance(employee_count, int):
                    employee_count = int(employee_count) if employee_count else 0

                in_range = lower_range <= employee_count <= upper_range
                has_ownership = (not ownership_data) or (
                    universal_name in ownership_data
                )
                is_new = universal_name not in current_universalnames

                if in_range and has_ownership and is_new:
                    current_universalnames.add(universal_name)
                    await queue.put(response)

        active_consumers = {asyncio.create_task(consume_stream(False, True))}

        check = await check_task_completion(state, "FAME")

        if check == "missing" or check == "famous":
            active_consumers.add(asyncio.create_task(consume_stream(True, True)))

        # active_consumers.add(asyncio.create_task(consume_stream(False, False)))

        queue_getter = asyncio.create_task(queue.get())

        while active_consumers:
            done, _ = await asyncio.wait(
                active_consumers | {queue_getter},
                return_when=asyncio.FIRST_COMPLETED,
            )

            if queue_getter in done:
                item = queue_getter.result()
                yield item
                queue_getter = asyncio.create_task(queue.get())

            finished = active_consumers & done
            active_consumers -= finished

        if not queue_getter.done():
            queue_getter.cancel()
        else:
            last_item = queue_getter.result()
            yield last_item

        pruning, locations = await asyncio.gather(
            *[
                check_task_completion(state, "PRUNING"),
                check_task_completion(state, "LOCATION"),
            ]
        )
        (
            lower_employee_count,
            upper_employee_count,
            company_ownership_status,
            company_ownership_data,
        ) = pruning

        industry_filter_company_count = 0
        if len(current_universalnames) < 50 and (
            (lower_range != 0 or upper_range != 9999999)
            or (company_ownership_status != [])
        ):
            (
                industry_and_special_criteria,
                industry_keywords,
            ) = await check_task_completion(state, "KEYWORDS")
            industry_boolean = industry_and_special_criteria["industries"]
            special_criteria = industry_and_special_criteria["special_criteria"]

            if special_criteria:
                pass
            else:
                remaining_count = 50 - len(current_universalnames)

                if lower_range == 0 and upper_range == 9999999:
                    lower_range = lower_employee_count
                    upper_range = upper_employee_count

                if not company_ownership:
                    ownership_data = company_ownership_data
                elif not ownership_data and company_ownership:
                    ownership_data = await check_task_completion(state, "OWNERSHIP")

                if not industry_boolean:
                    industry_keywords = []

                industry_filter_companies = await get_companies_by_industry(
                    industries=industry_boolean,
                    industry_keywords=industry_keywords,
                    locations=locations,
                    employee_lower=lower_range,
                    employee_upper=upper_range,
                    company_ownership_status=company_ownership_status,
                    generated_companies=list(current_universalnames),
                    es_client=es_client,
                )

                for company in industry_filter_companies:
                    company["type"] = "CURRENT"
                    yield f"data: {json.dumps(company, ensure_ascii=False)}\n\n"
                    industry_filter_company_count += 1
                    remaining_count -= 1
                    if remaining_count == 0:
                        break

        if len(current_universalnames) + industry_filter_company_count == 0:
            async for response in process_stream(
                current_prompt,
                es_client,
                context,
                "CURRENT",
                state,
                mysql_pool,
                redis_client,
                use_websearch=True,
                product_filter=product_filter,
                reasoning=True,
            ):
                yield response

    async def stream_past(lower_range, upper_range, company_ownership):
        ownership_data = None
        past_universalnames = set()

        if not past_prompt:
            return

        queue = asyncio.Queue()

        async def consume_stream(paraphrasing, reasoning):
            nonlocal lower_range, upper_range, ownership_data
            async for response in process_stream(
                past_prompt,
                es_client,
                context,
                "PAST",
                state,
                mysql_pool,
                redis_client,
                use_websearch=False,
                paraphrasing=paraphrasing,
                product_filter=product_filter,
                reasoning=reasoning,
            ):
                text = str(response)
                if "data: {" not in text:
                    continue

                data = json.loads(text[text.find("{") : text.rfind("}") + 1])
                employee_count = data.get("es_data", {}).get("employCount", 0)
                universal_name = data.get("es_data", {}).get("universalName", "")

                if not employee_count or not universal_name:
                    continue

                if (
                    lower_range == 0 and upper_range == 9999999
                ) or company_ownership == []:
                    (
                        lower_employee_count,
                        upper_employee_count,
                        _,
                        company_ownership_data,
                    ) = await check_task_completion(state, "PRUNING")
                    if lower_range == 0 and upper_range == 9999999:
                        lower_range = lower_employee_count
                        upper_range = upper_employee_count
                    if company_ownership == []:
                        ownership_data = company_ownership_data

                if not ownership_data and company_ownership:
                    ownership_data = await check_task_completion(state, "OWNERSHIP")

                if not isinstance(employee_count, int):
                    employee_count = int(employee_count) if employee_count else 0

                in_range = lower_range <= employee_count <= upper_range
                has_ownership = (not ownership_data) or (
                    universal_name in ownership_data
                )
                is_new = universal_name not in past_universalnames

                if in_range and has_ownership and is_new:
                    past_universalnames.add(universal_name)
                    await queue.put(response)

        active_consumers = {asyncio.create_task(consume_stream(False, True))}

        check = await check_task_completion(state, "FAME")

        if check == "missing" or check == "famous":
            active_consumers.add(asyncio.create_task(consume_stream(True, True)))

        # active_consumers.add(asyncio.create_task(consume_stream(False, False)))

        queue_getter = asyncio.create_task(queue.get())

        while active_consumers:
            done, _ = await asyncio.wait(
                active_consumers | {queue_getter},
                return_when=asyncio.FIRST_COMPLETED,
            )

            if queue_getter in done:
                item = queue_getter.result()
                yield item
                queue_getter = asyncio.create_task(queue.get())

            finished = active_consumers & done
            active_consumers -= finished

        if not queue_getter.done():
            queue_getter.cancel()
        else:
            last_item = queue_getter.result()
            yield last_item

        pruning, locations = await asyncio.gather(
            *[
                check_task_completion(state, "PRUNING"),
                check_task_completion(state, "LOCATION"),
            ]
        )
        (
            lower_employee_count,
            upper_employee_count,
            company_ownership_status,
            company_ownership_data,
        ) = pruning

        industry_filter_company_count = 0
        if len(past_universalnames) < 50 and (
            (lower_range != 0 or upper_range != 9999999)
            or (company_ownership_status != [])
        ):
            (
                industry_and_special_criteria,
                industry_keywords,
            ) = await check_task_completion(state, "KEYWORDS")
            industry_boolean = industry_and_special_criteria["industries"]
            special_criteria = industry_and_special_criteria["special_criteria"]

            if special_criteria:
                pass
            else:
                remaining_count = 50 - len(past_universalnames)

                if lower_range == 0 and upper_range == 9999999:
                    lower_range = lower_employee_count
                    upper_range = upper_employee_count

                if not company_ownership:
                    ownership_data = company_ownership_data
                elif not ownership_data and company_ownership:
                    ownership_data = await check_task_completion(state, "OWNERSHIP")

                if not industry_boolean:
                    industry_keywords = []

                industry_filter_companies = await get_companies_by_industry(
                    industries=industry_boolean,
                    industry_keywords=industry_keywords,
                    locations=locations,
                    employee_lower=lower_range,
                    employee_upper=upper_range,
                    company_ownership_status=company_ownership_status,
                    generated_companies=list(past_universalnames),
                    es_client=es_client,
                )

                for company in industry_filter_companies:
                    company["type"] = "PAST"
                    yield f"data: {json.dumps(company, ensure_ascii=False)}\n\n"
                    industry_filter_company_count += 1
                    remaining_count -= 1
                    if remaining_count == 0:
                        break

        if len(past_universalnames) + industry_filter_company_count == 0:
            async for response in process_stream(
                past_prompt,
                es_client,
                context,
                "PAST",
                state,
                mysql_pool,
                redis_client,
                use_websearch=True,
                product_filter=product_filter,
                reasoning=True,
            ):
                yield response

    queue = asyncio.Queue()

    async def collect_streams(lower_range, upper_range, company_ownership):
        """
        Collect responses from both current and past streams and put them in the queue.

        This function runs both stream processors concurrently and collects their
        responses into a single queue for interleaved processing.
        """
        current_gen = stream_current(lower_range, upper_range, company_ownership)
        past_gen = stream_past(lower_range, upper_range, company_ownership)

        async def collect_from(generator):
            """
            Collect responses from a generator and put them in the queue.

            Args:
                generator: The async generator to collect responses from
            """
            async for response in generator:
                await queue.put(response)

        await asyncio.gather(collect_from(past_gen), collect_from(current_gen))

        await queue.put(None)

    asyncio.create_task(collect_streams(lower_range, upper_range, company_ownership))

    universal_names = []
    try:
        while True:
            response = await queue.get()
            if response is None:
                break
            yield response
            iterator = iterator + 1
            try:
                universal_names.append(
                    (
                        response.split('"universalName":')[1]
                        .split(",")[0]
                        .strip()
                        .strip('"')
                    )
                )
            except:
                pass
            await asyncio.sleep(0.1)
    finally:
        await state.cleanup()
