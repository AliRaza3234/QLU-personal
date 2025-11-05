import asyncio, re, json
from qutils.qopenai.openai_utils import chatgpt_streaming_a

# from qutils.llm.utilities import asynchronous_llm
from qutils.llm.asynchronous import invoke


from app.utils.aisearch_expansion_variants.prompts import *
from app.utils.search.aisearch.company.generation.utilities import (
    post_process_gpt_output,
)
from app.utils.search.aisearch.company.generation.elastic import get_company_source
from app.utils.search.aisearch.company.generation.mapping import white_death_v2


tasks_imp = {}


def process_line(line):
    line = line.strip()
    match = re.search(r"^\d+\.\s*(.*)", line.split("~")[0])
    if match:
        name = match.group(1)
        location = line.split("~")[1]
        parts = line.split("~")
        try:
            industry = [parts[item] for item in range(2, len(parts))]
        except:
            industry = []
        return (name, location, str(industry))
    else:
        return None


# async def initialize_tasks(userquery, query_id):
#     tasks_imp[query_id] = {
#         "INDUSTRIES": asyncio.create_task(cache_industry(userquery))
#     }

# async def cache_industry(industries):

#     query_industries = tuple(industries)
#     target_count = 6

#     query = f"""SELECT name, location, total_counts, universal_name
#             FROM (
#                 SELECT name, industry, location, universal_name,
#                     SUM(counts) OVER (PARTITION BY name, location) AS total_counts
#                 FROM company_mapping_universalname
#                 WHERE
#                 {f'industry IN {query_industries}' if query_industries else ''}
#             ) AS subquery
#             WHERE total_counts >= {target_count}
#             GROUP BY name, location, total_counts, universal_name
#             {f'HAVING COUNT(DISTINCT industry) = {len(query_industries)}' if query_industries else ''};"""
#     global_cache = await postgres_fetch_all(query)
#     hashmap = {}

#     if global_cache:
#         for i in global_cache:
#             hashmap[(i[0], i[1])] = i

#     return industries[0], hashmap


async def industry_generator(prompt):
    user_prompt = f"""
            <Task>
                - Based on the user query : "{prompt}" give me a list of industries that would be relevant for finding such companies.
                - Make sure to only generate 1 to 3 industries which are the most relevant to look at.
                - The amount is dependant on the open ended nature of the query, if more are required to cover the query you may generate more.
                - If only a company is mentioned that you dont know in the prompt, return an empty list.
            </Task>

            <Output>
                - First give your thought process in one line then give the list of industries.
                - Give your output in the form <prediction>["industry 1", "industry 2", ...]</prediction>.
            </Output>
        """

    response = await invoke(
        messages=[
            {
                "role": "system",
                "content": "You are a relevant industry name generating agent.",
            },
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        model="openai/gpt-4o-mini",
        fallbacks=["openai/gpt-4o-mini"],
    )
    return post_process_gpt_output(response)


async def check_task_completion(type, query_id):
    task = tasks_imp[query_id][type]
    while not task.done():
        await asyncio.sleep(0.1)
    return task.result()


async def process_companies_v2(
    line,
    prompt,
    client,
    industries=None,
    esIds=[],
    output_type="CURRENT",
    hashmap={},
):

    processed_line = process_line(line)
    processed_line = list(processed_line)
    if len(processed_line) > 2:
        industries = processed_line[2]
    processed_line[1] = "United States"
    processed_line = tuple(processed_line)
    es_id, source = await white_death_v2(
        prompt, processed_line[0], industries, client, hashmap
    )

    if es_id and source:
        response = await get_company_source(es_id, source)
        if response and (response["es_id"] not in esIds):
            data = {
                "es_data": response,
                "list": processed_line[0],
                "excluded": False,
                "type": output_type,
            }
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def dual_strategies_v2(
    current_prompt,
    past_prompt,
    es_client,
):
    userquery = current_prompt if current_prompt and not past_prompt else past_prompt

    # query_id = str(uuid.uuid4())
    # asyncio.create_task(initialize_tasks(userquery, query_id))

    async def stream_current():
        if current_prompt:
            async for response in process_stream_v2(
                current_prompt, es_client, "CURRENT", ""
            ):
                yield response

    async def stream_past():
        if past_prompt:
            async for response in process_stream_v2(past_prompt, es_client, "PAST", ""):
                yield response

    queue = asyncio.Queue()

    async def collect_streams():
        current_gen = stream_current()
        past_gen = stream_past()

        async def collect_from(generator):
            async for response in generator:
                await queue.put(response)

        await asyncio.gather(collect_from(past_gen), collect_from(current_gen))

        await queue.put(None)

    asyncio.create_task(collect_streams())

    while True:
        response = await queue.get()
        if response is None:
            break
        yield response
        await asyncio.sleep(0.1)


async def process_stream_v2(prompt, es_client, output_type="CURRENT", query_id=None):

    line = ""
    background_tasks = []
    flag = False
    failsafe = 70
    async for result in generate_companies_v2(prompt):
        line += result
        if "<companies>" in line.lower():
            flag = True
            line = ""
        if flag and result == "\n":
            line = re.sub(r"^.*?(\d.*)", r"\1", line, flags=re.DOTALL)
            # result = await check_task_completion("INDUSTRIES", query_id)
            # (industries, hashmap) = result
            task = asyncio.create_task(
                process_companies_v2(
                    line,
                    prompt,
                    es_client,
                    None,
                    output_type=output_type,
                    hashmap=None,
                )
            )
            background_tasks.append(task)
            line = ""
            failsafe += 5

    while background_tasks:
        if len(background_tasks) == 0 or failsafe < 0:
            break
        task = background_tasks.pop(0)
        if task.done():
            response = task.result()
            if isinstance(response, list):
                for res in response:
                    yield res
            elif isinstance(response, str):
                yield response
        else:
            background_tasks.append(task)
        failsafe -= 1


async def generate_companies_v2(prompt):
    user_prompt = (
        GENERATE_COMPANIES_USER_PROMPT
        + f"""
        <Prompt>
            {prompt}
        </Prompt>
        <Size Range>
            The companies size range isnt mentioned or required so you should disregard it.
        </Size Range>
    """
    )

    description_chat = [
        {"role": "system", "content": GENERATE_COMPANIES_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    async for desc_chunk in chatgpt_streaming_a(
        messages=description_chat, temperature=0, model="gpt-4o"
    ):
        yield desc_chunk
