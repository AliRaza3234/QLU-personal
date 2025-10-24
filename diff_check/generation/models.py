import os
import asyncio
from openai import AsyncOpenAI
from qutils.llm.asynchronous import stream
from app.utils.search.aisearch.company.generation.prompts import (
    GENERATION_SYSTEM_PROMPT,
    GENERATION_SYSTEM_PROMPT_NON_REASONING,
    GENERATION_SYSTEM_PROMPT_GPT5,
    COGNITO_PATHFINDER,
    COGNITO_SCOUT,
    COGNITO_CONNECTOR,
    COGNITO_FAST,
)


async def generation(messages, temperature, model):
    buffer = ""
    in_companies_tag = False

    async for chunk in stream(
        messages=messages,
        temperature=temperature,
        model=model,
        top_p=0.7,
    ):
        buffer += chunk

        if not in_companies_tag and "<companies>" in buffer.lower():
            in_companies_tag = True
            buffer = buffer[buffer.lower().index("<companies>") + len("<companies>") :]

        if in_companies_tag:
            if "</companies>" in buffer.lower():
                remaining = buffer[: buffer.lower().index("</companies>")]
                lines = remaining.strip().split("\n")
                for line in lines:
                    line = line.strip()
                    if line and "~" in line:
                        yield line
                break

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if line and "~" in line:
                    yield line


async def gpt5_generation(query, reasoning=True):
    buffer = ""
    in_companies_tag = False

    if reasoning:
        system_prompt = GENERATION_SYSTEM_PROMPT_GPT5
    else:
        system_prompt = GENERATION_SYSTEM_PROMPT_NON_REASONING

    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    stream_manager = client.responses.stream(
        model="gpt-5",
        input=[
            {
                "role": "developer",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": query}],
            },
        ],
        text={"format": {"type": "text"}, "verbosity": "medium"},
        reasoning={"effort": "minimal" if reasoning else "none", "summary": "auto"},
        tools=[],
        store=False,
        include=[],
    )

    async with stream_manager as stream_response:
        async for event in stream_response:
            if event.type == "response.output_text.delta":
                chunk = event.delta
                buffer += chunk

                if not in_companies_tag and "<companies>" in buffer.lower():
                    in_companies_tag = True
                    buffer = buffer[
                        buffer.lower().index("<companies>") + len("<companies>") :
                    ]

                if in_companies_tag:
                    if "</companies>" in buffer.lower():
                        remaining = buffer[: buffer.lower().index("</companies>")]
                        lines = remaining.strip().split("\n")
                        for line in lines:
                            line = line.strip()
                            if line and "~" in line:
                                yield line
                        break

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if line and "~" in line:
                            yield line


async def merge_aiters(*aiters):
    aiter_objs = [ait.__aiter__() for ait in aiters]
    pending = {
        asyncio.create_task(ait.__anext__()): idx for idx, ait in enumerate(aiter_objs)
    }

    while pending:
        done, _ = await asyncio.wait(
            pending.keys(), return_when=asyncio.FIRST_COMPLETED
        )
        for task in done:
            idx = pending.pop(task)
            try:
                item = task.result()
            except StopAsyncIteration:
                continue
            else:
                pending[asyncio.create_task(aiter_objs[idx].__anext__())] = idx
                yield idx, item


async def model_company_stream(query, model, reasoning, ideal_companies=None):
    if reasoning == False:
        system = GENERATION_SYSTEM_PROMPT_NON_REASONING
    else:
        system = GENERATION_SYSTEM_PROMPT

    if ideal_companies and model not in ["openai/gpt-4.1", "openai/gpt-5"]:
        query = query + f"\nIdeal Companies: {', '.join(ideal_companies)}"

    async for company in generation(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": query},
        ],
        temperature=0.4,
        model=model,
    ):
        yield company, model


async def gpt5_company_stream(query, reasoning, ideal_companies=None):
    async for company_line in gpt5_generation(query, reasoning):
        yield company_line, "openai/gpt-5"


async def gpt41_leader_stream(prompt, reasoning, gpt41_queue):
    ideal_companies = []
    ideal_companies_set = asyncio.Event()

    async def stream_gpt41():
        async for company_line in generation(
            messages=[
                {
                    "role": "system",
                    "content": (
                        GENERATION_SYSTEM_PROMPT
                        if reasoning
                        else GENERATION_SYSTEM_PROMPT_NON_REASONING
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            model="openai/gpt-4.1",
        ):
            parts = company_line.split("~")
            if len(parts) >= 2:
                try:
                    name = parts[0].strip()
                    score = int(parts[1].strip())

                    if score >= 18 and len(ideal_companies) < 5:
                        ideal_companies.append(name)
                        if len(ideal_companies) == 5:
                            ideal_companies_set.set()

                    await gpt41_queue.put((company_line, "openai/gpt-4.1"))
                except (IndexError, ValueError):
                    continue

        ideal_companies_set.set()
        await gpt41_queue.put(("gpt41_leader", None))

    asyncio.create_task(stream_gpt41())

    return ideal_companies, ideal_companies_set


async def gpt5_leader_stream(prompt, reasoning, gpt5_queue):
    async def stream_gpt5():
        async for company_line in gpt5_generation(prompt, reasoning):
            parts = company_line.split("~")
            if len(parts) >= 2:
                try:
                    await gpt5_queue.put((company_line, "openai/gpt-5"))
                except (IndexError, ValueError):
                    continue

        await gpt5_queue.put(("gpt5", None))

    asyncio.create_task(stream_gpt5())


async def generate_companies_multimodel(prompt, reasoning=True):
    other_models = ["groq/openai/gpt-oss-120b", "groq/moonshotai/kimi-k2-instruct-0905"]

    model_thresholds = {
        "openai/gpt-5": 17,
        "openai/gpt-4.1": 17,
        "groq/openai/gpt-oss-120b": 18,
        "groq/moonshotai/kimi-k2-instruct-0905": 18,
    }

    seen_companies = set()
    gpt41_queue = asyncio.Queue()
    gpt5_queue = asyncio.Queue()

    yield "<companies>\n"

    ideal_companies, ideal_companies_set = await gpt41_leader_stream(
        prompt, reasoning, gpt41_queue
    )

    await gpt5_leader_stream(prompt, reasoning, gpt5_queue)

    async def start_other_models():
        await ideal_companies_set.wait()

        gens = [
            model_company_stream(prompt, m, reasoning, ideal_companies)
            for m in other_models
        ]

        async for _, item in merge_aiters(*gens):
            await gpt41_queue.put(item)

        await gpt41_queue.put(("other_models", None))

    asyncio.create_task(start_other_models())

    async def merge_queues():
        completed_queues = {"gpt41": False, "gpt5": False}

        while not all(completed_queues.values()):
            tasks = []
            task_to_queue = {}

            if not completed_queues["gpt41"]:
                task = asyncio.create_task(gpt41_queue.get())
                tasks.append(task)
                task_to_queue[task] = "gpt41"

            if not completed_queues["gpt5"]:
                task = asyncio.create_task(gpt5_queue.get())
                tasks.append(task)
                task_to_queue[task] = "gpt5"

            if not tasks:
                break

            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )

            for task in done:
                queue_name = task_to_queue[task]
                item = task.result()

                if isinstance(item, tuple) and len(item) == 2 and item[1] is None:
                    completed_queues[queue_name] = True
                    continue

                if item is None:
                    completed_queues[queue_name] = True
                    continue

                company_line, model = item
                parts = company_line.split("~")
                if len(parts) < 2:
                    continue

                try:
                    name = parts[0].strip()
                    score = int(parts[1].strip())
                except (IndexError, ValueError):
                    continue

                threshold = model_thresholds.get(model, 18)
                if score >= threshold and name not in seen_companies:
                    seen_companies.add(name)
                    yield f"{name} ~ {score}\n"

            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    async for result in merge_queues():
        yield result

    yield "</companies>\n"


async def generate_companies(prompt, reasoning=True):
    async for result in generate_companies_multimodel(prompt, reasoning):
        yield result


async def generate_companies_by_cognito(company_prompt, reasoning=False):
    system_prompts = [
        COGNITO_PATHFINDER,
        COGNITO_SCOUT,
        COGNITO_CONNECTOR,
        COGNITO_FAST,
    ]
    """
    Simplified parallel company generation that streams only unique company names.
    Runs three agents in parallel and yields unique company names as they are discovered.
    
    Args:
        company_prompt: The user prompt for company generation
        system_prompts: List of 3 system prompts for different agents
    
    Yields:
        str: Unique company names as they are discovered
    """

    # Shared state for duplicate detection
    shared_companies_set = set()
    shared_lock = asyncio.Lock()

    START_TAG = "<stream_company_name>"
    END_TAG = "</stream_company_name>"

    async def process_agent_stream(system_prompt: str):
        """Process a single agent's stream and extract company names"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": company_prompt},
        ]

        response_buffer = ""

        try:
            llm_stream = stream(
                messages=messages,
                model="openai/gpt-4.1",
                temperature=1,
                max_tokens=4096,
            )

            async for chunk in llm_stream:
                response_buffer += chunk

                # Check for complete company name tags
                while True:
                    start_index = response_buffer.find(START_TAG)
                    if start_index == -1:
                        break

                    end_index = response_buffer.find(END_TAG, start_index)
                    if end_index == -1:
                        break

                    # Extract company name
                    company_name_start_pos = start_index + len(START_TAG)
                    company_name = response_buffer[
                        company_name_start_pos:end_index
                    ].strip()

                    if company_name:
                        # Thread-safe duplicate checking
                        async with shared_lock:
                            if company_name.lower() not in {
                                c.lower() for c in shared_companies_set
                            }:
                                shared_companies_set.add(company_name)
                                yield f"{company_name} ~ 20\n"

                    # Remove processed part from buffer
                    response_buffer = response_buffer[end_index + len(END_TAG) :]

        except Exception:
            pass  # Silently handle errors

    # Create async generators for all three agents
    agent_generators = [process_agent_stream(prompt) for prompt in system_prompts]

    yield "<companies>\n"
    # Merge all streams and yield company names as they arrive
    async for _, company_name in merge_aiters(*agent_generators):
        yield company_name
    yield "</companies>\n"
