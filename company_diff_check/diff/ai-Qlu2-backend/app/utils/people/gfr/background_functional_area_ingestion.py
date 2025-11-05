import os
import asyncio
from elasticsearch import helpers
from collections import defaultdict

from app.utils.etl.functional_areas import get_functional_area
from app.utils.people.gfr.global_state import (
    deregister_task,
    register_task,
    is_task_running,
)
from qutils.database.post_gres import DatabaseConnection


async def get_profiles(esIds, connection):
    body = {
        "size": 10000,
        "query": {
            "bool": {
                "must": [
                    {"terms": {"_id": esIds}},
                    {
                        "nested": {
                            "path": "experience",
                            "query": {
                                "bool": {
                                    "must": [
                                        {"term": {"experience.index": 0}},
                                        {
                                            "bool": {
                                                "must_not": {
                                                    "exists": {
                                                        "field": "experience.functional_area"
                                                    }
                                                }
                                            }
                                        },
                                    ]
                                }
                            },
                        }
                    },
                ]
            }
        },
    }
    results = await connection.search(
        index=os.environ.get("ES_PROFILES_INDEX", "profiles"), body=body
    )

    return results


async def ingest_all_results(es, all_data):
    data_to_upload = []
    for es_id, source in all_data.items():
        action = {
            "_op_type": "index",
            "_index": os.environ.get("ES_PROFILES_INDEX", "profiles"),
            "_id": es_id,
            "_source": source,
        }

        data_to_upload.append(action)

    if len(data_to_upload) > 0:
        await helpers.async_bulk(es, data_to_upload)


async def ingest_after_postgre(responses, connection):
    data_to_upload = []
    for response in responses:
        action = {
            "_op_type": "index",
            "_index": "profile",
            "_id": response["_id"],
            "_source": response["_source"],
        }
        data_to_upload.append(action)

    if len(data_to_upload) > 0:
        await helpers.async_bulk(connection, data_to_upload)


async def ingest_temp_data_with_update(connection, functionalAreas_dict):
    es_ids = []
    db = DatabaseConnection()
    con = await db.get_database_connection_fs()

    data_tuples = []
    for profile_id, entries in functionalAreas_dict.items():
        for entry in entries:
            index = entry["index"]
            functional_area = entry["functional_area"]
            data_tuples.append((profile_id, index, functional_area))

    async with con.cursor() as cursor:
        await cursor.execute(
            """
                DROP TABLE IF EXISTS temp_functional_updates;
                CREATE TEMP TABLE temp_functional_updates (
                    profile_id VARCHAR(255),
                    index INT,
                    functional_area VARCHAR(255)
                );
            """
        )
        await cursor.executemany(
            """
                INSERT INTO temp_functional_updates (profile_id, index, functional_area)
                VALUES (%s, %s, %s)
            """,
            data_tuples,
        )
        await con.commit()

        await cursor.execute(
            """
                UPDATE profile_experience AS pe
                SET functional_area = tpu.functional_area
                FROM temp_functional_updates AS tpu
                WHERE pe.profile_id = tpu.profile_id
                AND pe.index = tpu.index;
            """
        )
        await con.commit()
    await cursor.close()
    await con.close()

    es_ids = list(functionalAreas_dict.keys())
    query = {"query": {"terms": {"_id": es_ids}}}
    responses = await connection.search(
        body=query, index=os.getenv("ES_PROFILES_INDEX")
    )

    for data_tuple in data_tuples:
        profile_id, index, functional_area = data_tuple

        for response in responses["hits"]["hits"]:
            if response["_id"] == profile_id:
                response["_source"]["experience"][index][
                    "functional_area"
                ] = functional_area

    await ingest_after_postgre(responses["hits"]["hits"], connection)


async def alter_and_ingest(connection, total_results, functional_areas, universal_name):
    total_data = {}

    for es_id, _source in total_results.items():
        current_experiences = []
        for experience in _source["experience"]:
            if (
                (experience["end"] == None)
                and (experience["functional_area"] == None)
                and (experience["company_universal_name"] == universal_name)
            ):
                current_experiences.append(
                    {
                        "headline": _source["headline"],
                        "title": experience["title"],
                        "universal_name": experience["company_universal_name"],
                        "functional_areas": functional_areas,
                        "index": experience["index"],
                    }
                )
        if current_experiences:
            total_data[es_id] = current_experiences

    tasks = []
    key_index_list = []

    for key, experiences in total_data.items():
        for experience in experiences:
            tasks.append(get_functional_area(experience))
            key_index_list.append((key, experience["index"]))

    functionalAreas_returned = await asyncio.gather(*tasks)
    functionalAreas_dict = defaultdict(list)
    for (key, index), result in zip(key_index_list, functionalAreas_returned):
        functionalAreas_dict[key].append({"index": index, "functional_area": result})
    functionalAreas_dict = dict(functionalAreas_dict)
    await ingest_temp_data_with_update(connection, functionalAreas_dict)


async def ingest(esIds, functional_areas, task_id, client):
    try:
        results = await get_profiles(esIds, client)
        total_results = {}
        for result in results["hits"]["hits"]:
            total_results[result["_id"]] = result["_source"]

            if len(total_results) % 10 == 0:
                await alter_and_ingest(client, total_results, functional_areas, task_id)
                total_results = {}

        if len(total_results) > 0:
            await alter_and_ingest(client, total_results, functional_areas, task_id)
            total_results = {}

    finally:
        deregister_task(task_id)


async def custom_ingestion_task_creator(data, functional_area, task_id, client):
    if not is_task_running(task_id):
        task = asyncio.create_task(ingest(data, functional_area, task_id, client))
        register_task(task_id, task)
    else:
        pass


async def modify_functional_area_flag(universal_name, client):
    try:
        result = await client.count(
            index=os.environ.get("ES_PROFILES_INDEX", "profiles"),
            body={
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
                                                    "match": {
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
                }
            },
        )
        if result["count"] >= 1000:
            company_source = await client.search(
                body={
                    "query": {"term": {"li_universalname": universal_name}},
                },
                index=os.getenv("ES_COMPANIES_INDEX"),
            )

            for i in company_source["hits"]["hits"]:
                if "functional_area_flag" in i["_source"]:
                    if i["_source"]["functional_area_flag"]:
                        break

                i["_source"]["functional_area_flag"] = True

                try:
                    await client.index(
                        index=os.getenv("ES_COMPANIES_INDEX"),
                        id=i["_id"],
                        document=i["_source"],
                    )
                except AssertionError as exception:
                    print(f"AssertionError occurred while indexing: {exception}")
                except Exception as exception:
                    print(f"An error occurred while indexing: {exception}")

    except Exception as exception:
        print(f"Error while modifying functional area flag: {exception}")
