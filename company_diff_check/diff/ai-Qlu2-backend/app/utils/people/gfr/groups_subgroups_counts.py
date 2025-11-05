import os
import asyncio

from app.utils.etl.functional_areas import search_functional_area
from app.utils.people.gfr.utilities import ranking_data, get_ranked_esIds, counter
from app.utils.people.gfr.background_functional_area_ingestion import (
    custom_ingestion_task_creator,
)


async def get_search_strings(universal_name, group_name, client):
    body = {"query": {"term": {"li_universalname": {"value": universal_name}}}}
    data = await client.search(index="groups_company", body=body)
    groups_data = data["hits"]["hits"][0]["_source"]["groups"]
    output = {}
    for group in groups_data:
        if group["name"] == group_name:
            for sg in group["sub_groups"]:
                search_strings = []
                search_strings.append(sg["name"])
                if sg["sub_sub_groups"]:
                    search_strings.extend(sg["sub_sub_groups"])
                output[sg["name"]] = search_strings
    return output


async def get_all_search_strings(universal_name, client):
    body = {"query": {"term": {"li_universalname": {"value": universal_name}}}}
    data = await client.search(index="groups_company", body=body)
    groups_data = data["hits"]["hits"][0]["_source"]["groups"]
    mapping = {}
    sgs = []
    for data in groups_data:
        temporary = {}
        for i in data["sub_groups"]:
            sgs.append(i["name"])
            try:
                sub_sub_groups_with_name = i["sub_sub_groups"] + [i["name"]]
            except:
                sub_sub_groups_with_name = [i["name"]]
            temporary[i["name"]] = sub_sub_groups_with_name
        mapping[data["name"]] = temporary
    return mapping


async def get_sg_counts(payload, client):
    universal_name = payload["universal_name"]

    tasks = []
    tasks.append(search_functional_area(universal_name))
    for rank in ranking_data.keys():
        tasks.append(get_ranked_esIds(ranking_data, rank, universal_name, client))
    tasks.append(get_all_search_strings(universal_name, client))

    es_data = await asyncio.gather(*tasks)
    functional_areas = es_data[0]

    try:
        functional_areas = functional_areas[0]
    except:
        functional_areas = []

    groups = es_data[-1]

    ids_list = [item for sublist in es_data[1 : len(es_data) - 1] for item in sublist]

    if os.getenv("ENVIRONMENT") == "production":
        await custom_ingestion_task_creator(
            ids_list, functional_areas, universal_name, client
        )

    search_strings_groups = {}
    for key, value in groups.items():
        search_strings_groups[key] = [[k] + v for k, v in value.items()]

    tasks = []
    for key, value in search_strings_groups.items():
        for strings in value:
            tasks.append(counter(universal_name, strings, client, es_ids=ids_list))
    result = await asyncio.gather(*tasks)

    output = {}
    iterator = 0

    for category, products in groups.items():
        temp = {
            k: result[iterator + i]
            for i, (k, v) in enumerate(products.items())
            if result[iterator + i] != 0
        }
        iterator += len(products)
        if temp:
            output[category] = temp

    return output
