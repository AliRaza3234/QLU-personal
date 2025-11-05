import os
import asyncio
from app.utils.people.gfr.utilities import (
    ranking_data,
    get_ranked_esIds,
    search_query_generator,
    get_search_strings,
    get_profiles_by_function,
)


async def get_mapped_people_ranks(payload, client):
    type = payload["type"]
    limit = payload["limit"]
    filter = payload["filter"]
    offset = payload["offset"]
    universal_name = payload["universal_name"]
    sub_group_name = payload["sub_group_name"]

    if type == "rank":
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
        es_ids = master_data[filter]

    elif type == "function":
        tasks = []
        tasks.append(get_profiles_by_function(universal_name, filter, client))
        tasks.append(get_search_strings(universal_name, sub_group_name, client))
        es_data = await asyncio.gather(*tasks)

        search_strings = es_data[-1]
        ids_list = es_data[:-1]

        es_ids = [item for sublist in ids_list for item in sublist]

    query = search_query_generator(universal_name, search_strings, es_ids)
    query["from"] = offset
    query["size"] = limit
    query["_source"] = False

    response = await client.search(
        index=os.environ.get("ES_PROFILES_INDEX", "profiles"), body=query
    )
    response_ids = []
    for data in response["hits"]["hits"]:
        response_ids.append(data["_id"])
    return response_ids
