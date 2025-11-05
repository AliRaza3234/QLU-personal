import asyncio
from app.utils.people.gfr.utilities import counter, ranking_data, get_ranked_esIds


async def get_search_strings(universal_name, sub_group_name, client):
    data = await client.search(
        index="groups_company",
        body={"query": {"term": {"li_universalname": {"value": universal_name}}}},
    )
    groups_data = data["hits"]["hits"][0]["_source"]["groups"]
    search_strings = []
    condition = False
    for group in groups_data:
        for sg in group["sub_groups"]:
            if sub_group_name == sg["name"]:
                search_strings.append(sg["name"])
                if sg["sub_sub_groups"]:
                    search_strings.extend(sg["sub_sub_groups"])
                condition = True
                break
        if condition == True:
            break
    return search_strings


async def get_ranked_ids(payload, client):
    universal_name = payload["universal_name"]
    sub_group_name = payload["sub_group_name"]

    master_data = {}
    tasks = []

    for rank in ranking_data.keys():
        tasks.append(get_ranked_esIds(ranking_data, rank, universal_name, client))
    tasks.append(get_search_strings(universal_name, sub_group_name, client))
    es_data = await asyncio.gather(*tasks)

    search_strings = es_data[-1]
    ids_list = es_data[: len(list(ranking_data.keys()))]

    for index, ids in enumerate(ids_list):
        master_data[list(ranking_data.keys())[index]] = ids

    tasks = []
    for value in master_data.values():
        tasks.append(counter(universal_name, search_strings, client, es_ids=value))
    counts = await asyncio.gather(*tasks)

    response = {}
    iterator = 0
    for rank in ranking_data.keys():
        response[rank] = counts[iterator]
        iterator = iterator + 1

    return {key: value for key, value in response.items() if value != 0}
