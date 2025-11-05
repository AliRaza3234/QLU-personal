import os
import asyncio
from app.utils.people.gfr.utilities import (
    counter,
    get_search_strings,
)


async def get_functional_area_names(universal_name, client):
    query = {
        "size": 0,
        "query": {
            "bool": {
                "must": [
                    {
                        "nested": {
                            "path": "experience",
                            "query": {
                                "bool": {
                                    "must": [
                                        {"match": {"experience.index": "0"}},
                                        {
                                            "term": {
                                                "experience.company_universal_name": {
                                                    "value": universal_name
                                                }
                                            }
                                        },
                                    ]
                                }
                            },
                        }
                    }
                ]
            }
        },
        "aggs": {
            "filtered_experience": {
                "nested": {"path": "experience"},
                "aggs": {
                    "filtered_by_index": {
                        "filter": {"term": {"experience.index": "0"}},
                        "aggs": {
                            "uniqueFunctionalAreas": {
                                "terms": {
                                    "field": "experience.functional_area",
                                    "size": 10000,
                                    "min_doc_count": 3,
                                }
                            }
                        },
                    }
                },
            }
        },
    }
    data = await client.search(
        index=os.environ.get("ES_PROFILES_INDEX", "profiles"), body=query
    )
    functional_areas = []
    for function in data["aggregations"]["filtered_experience"]["filtered_by_index"][
        "uniqueFunctionalAreas"
    ]["buckets"]:
        functional_areas.append(function["key"])
    return functional_areas


async def get_profiles_by_function(
    universal_name, function, client, limit=None, offset=None
):
    query = {
        "_source": False,
        "query": {
            "bool": {
                "must": [
                    {
                        "nested": {
                            "path": "experience",
                            "query": {
                                "bool": {
                                    "must": [
                                        {
                                            "match_phrase": {
                                                "experience.functional_area": function
                                            }
                                        },
                                        {"match_phrase": {"experience.index": "0"}},
                                        {
                                            "match_phrase": {
                                                "experience.company_universal_name": universal_name
                                            }
                                        },
                                    ]
                                }
                            },
                        }
                    }
                ]
            }
        },
    }

    if limit:
        query["size"] = limit
        query["from"] = offset
    else:
        query["size"] = 10000

    data = await client.search(
        index=os.environ.get("ES_PROFILES_INDEX", "profiles"), body=query
    )
    ids = []
    for profile in data["hits"]["hits"]:
        ids.append(profile["_id"])
    return ids


async def get_functional_ids(payload, client):
    universal_name = payload["universal_name"]
    sub_group_name = payload["sub_group_name"]

    functional_areas = await get_functional_area_names(universal_name, client)

    tasks = []
    for function in functional_areas:
        tasks.append(get_profiles_by_function(universal_name, function, client))
    tasks.append(get_search_strings(universal_name, sub_group_name, client))
    es_data = await asyncio.gather(*tasks)

    search_strings = es_data[-1]
    functional_es_ids = es_data[: len(functional_areas)]

    function_map = {}
    for index, function in enumerate(functional_areas):
        function_map[function] = functional_es_ids[index]

    tasks = []
    for value in function_map.values():
        tasks.append(
            counter(
                universal_name,
                search_strings,
                client,
                es_ids=value,
            )
        )
    counts = await asyncio.gather(*tasks)

    response = {}
    for index, function in enumerate(functional_areas):
        response[function] = counts[index]
    return {key: value for key, value in response.items() if value != 0}
