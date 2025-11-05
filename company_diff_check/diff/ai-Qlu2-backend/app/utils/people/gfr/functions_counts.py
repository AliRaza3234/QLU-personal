import os


async def get_functions_counts(payload, client):
    universal_name = payload["universal_name"]
    master_data = {}
    result = await client.search(
        index=os.environ.get("ES_PROFILES_INDEX", "profiles"),
        body={
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
        },
    )

    for function in result["aggregations"]["filtered_experience"]["filtered_by_index"][
        "uniqueFunctionalAreas"
    ]["buckets"]:
        master_data[function["key"]] = function["doc_count"]
    return master_data
