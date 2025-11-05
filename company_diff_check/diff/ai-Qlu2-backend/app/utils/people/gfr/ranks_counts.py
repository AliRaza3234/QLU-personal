import os
import asyncio
import itertools
from app.utils.etl.functional_areas import search_functional_area
from app.utils.people.gfr.utilities import ranking_data, get_ranked_esIds
from app.utils.people.gfr.background_functional_area_ingestion import (
    custom_ingestion_task_creator,
    modify_functional_area_flag,
)


async def get_company_count_and_function_flag(universal_name, client):
    result = await client.search(
        index=os.getenv("ES_COMPANIES_INDEX"),
        body={
            "_source": ["li_size", "functional_area_flag"],
            "query": {"term": {"li_universalname": {"value": universal_name}}},
        },
    )

    flag = False
    if "functional_area_flag" in str(result):
        flag = result["hits"]["hits"][0]["_source"]["functional_area_flag"]

    try:
        return int(result["hits"]["hits"][0]["_source"]["li_size"]), flag
    except:
        return 1000, flag


async def get_rank_counts(payload, client):
    universal_name = payload["universal_name"]

    if os.getenv("ENVIRONMENT") == "production":
        asyncio.create_task(modify_functional_area_flag(universal_name, client))

    tasks = []
    tasks.append(search_functional_area(universal_name))
    for rank in ranking_data.keys():
        tasks.append(get_ranked_esIds(ranking_data, rank, universal_name, client))
    tasks.append(get_company_count_and_function_flag(universal_name, client))
    es_data = await asyncio.gather(*tasks)

    functional_areas = es_data[0]
    try:
        functional_areas = functional_areas[0]
    except:
        functional_areas = []

    company_count_and_function_flag = es_data[-1]
    company_count = company_count_and_function_flag[0]
    function_flag = company_count_and_function_flag[1]
    es_data = es_data[1:-1]

    if function_flag == True and os.getenv("ENVIRONMENT") == "production":
        await custom_ingestion_task_creator(
            list(itertools.chain.from_iterable(es_data)),
            functional_areas,
            universal_name,
            client,
        )

    counts = [len(sublist) for sublist in es_data]

    master_data = {}

    threshold = 0
    if company_count >= 100000:
        threshold = 4
    elif company_count >= 50000:
        threshold = 3
    elif company_count >= 25000:
        threshold = 2
    else:
        threshold = 1

    for index, rank in enumerate(ranking_data.keys()):
        master_data[rank] = counts[index]

    return {key: value for key, value in master_data.items() if value >= threshold}
