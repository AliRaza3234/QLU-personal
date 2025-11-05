import os
from app.core.database import cache_data, get_cached_data, delete_cached_data
from app.utils.people.similar_profiles.extension.internal import (
    get_internal_similar_profiles,
)
from app.utils.people.similar_profiles.extension.external import (
    get_external_similar_profiles,
)


async def fetch_updated_at_es(ids, client, size=100):
    query = {
        "query": {"ids": {"values": ids}},
        "_source": ["updated_at"],
        "size": size,
    }
    index = os.environ.get("ES_PROFILES_INDEX", "profile")
    response = await client.search(index=index, body=query)

    updated_at_es = {}
    hits = response["hits"]["hits"]
    for hit in hits:
        _id = hit["_id"]
        updated_at_es[_id] = hit["_source"].get("updated_at", None)

    return updated_at_es


async def similar_profiles(payload, client, connector):
    _id = payload.esId
    type_ = payload.type
    offset = payload.offset
    limit = payload.limit

    input_profile_updated_at = await fetch_updated_at_es([_id], client, size=1)

    if type_ == "external":
        cached_data_with_timestamp = await get_cached_data(
            _id, "external_similar_profiles"
        )

        if cached_data_with_timestamp:
            cached_input_profile_updated_at = cached_data_with_timestamp.get(
                "input_profile_updated_at"
            )

            if cached_input_profile_updated_at and cached_input_profile_updated_at.get(
                _id
            ) == input_profile_updated_at.get(_id):
                cached_ids_with_experience = cached_data_with_timestamp.get(
                    "ids_with_experience"
                )
                cached_updated_at_es = cached_data_with_timestamp.get("updated_at")

                if cached_ids_with_experience and cached_updated_at_es:
                    cached_es_ids = [
                        item["esId"] for item in cached_ids_with_experience
                    ]

                    current_updated_at_es = await fetch_updated_at_es(
                        cached_es_ids, client, size=100
                    )

                    if all(
                        cached_updated_at_es.get(id) == current_updated_at_es.get(id)
                        for id in cached_es_ids
                    ):
                        start_index = offset
                        end_index = start_index + limit
                        already_paginated_response = cached_ids_with_experience[
                            start_index:end_index
                        ]
                        return already_paginated_response, len(
                            cached_ids_with_experience
                        )
            else:
                await delete_cached_data(_id, "external_similar_profiles")

        ids_with_experience = await get_external_similar_profiles(
            _id, client, connector
        )
        updated_at_es = {}

        if ids_with_experience:
            es_ids = [item["esId"] for item in ids_with_experience]
            updated_at_es = await fetch_updated_at_es(es_ids, client, size=100)

            await cache_data(
                _id,
                {
                    "input_profile_updated_at": input_profile_updated_at,
                    "ids_with_experience": ids_with_experience,
                    "updated_at": updated_at_es,
                },
                "external_similar_profiles",
                expiration_days=7,
            )
        else:
            return {"message": "Not Found"}

        start_index = offset
        end_index = start_index + limit
        paginated_response = ids_with_experience[start_index:end_index]

    elif type_ == "internal":
        cached_data_with_timestamp = await get_cached_data(
            _id, "internal_similar_profiles"
        )

        if cached_data_with_timestamp:
            cached_input_profile_updated_at = cached_data_with_timestamp.get(
                "input_profile_updated_at"
            )

            if cached_input_profile_updated_at and cached_input_profile_updated_at.get(
                _id
            ) == input_profile_updated_at.get(_id):
                cached_ids_with_experience = cached_data_with_timestamp.get(
                    "ids_with_experience"
                )
                cached_updated_at_es = cached_data_with_timestamp.get("updated_at")

                if cached_ids_with_experience and cached_updated_at_es:
                    cached_es_ids = [
                        item["esId"] for item in cached_ids_with_experience
                    ]

                    current_updated_at_es = await fetch_updated_at_es(
                        cached_es_ids, client, size=100
                    )

                    if all(
                        cached_updated_at_es.get(id) == current_updated_at_es.get(id)
                        for id in cached_es_ids
                    ):
                        start_index = offset
                        end_index = start_index + limit
                        already_paginated_response = cached_ids_with_experience[
                            start_index:end_index
                        ]
                        return already_paginated_response, len(
                            cached_ids_with_experience
                        )
            else:
                await delete_cached_data(_id, "internal_similar_profiles")

        ids_with_experience = await get_internal_similar_profiles(
            _id, client, connector
        )
        updated_at_es = {}

        if ids_with_experience:
            es_ids = [item["esId"] for item in ids_with_experience]
            updated_at_es = await fetch_updated_at_es(es_ids, client, size=100)

            await cache_data(
                _id,
                {
                    "input_profile_updated_at": input_profile_updated_at,
                    "ids_with_experience": ids_with_experience,
                    "updated_at": updated_at_es,
                },
                "internal_similar_profiles",
                expiration_days=7,
            )
        else:
            return {"message": "Not Found"}

        start_index = offset
        end_index = start_index + limit
        paginated_response = ids_with_experience[start_index:end_index]

    return paginated_response, len(ids_with_experience)
