import os
import asyncio
import datetime
import traceback
from fastapi import HTTPException
import json
from app.utils.people.similar_profiles.regular.internal import (
    get_internal_similar_profiles_ai_search,
    get_internal_similar_profiles_name_search,
    get_internal_similar_profiles_groups,
    get_internal_similar_profiles_rank,
    get_internal_similar_profiles_function,
)
from app.utils.people.similar_profiles.regular.external import (
    get_external_similar_profiles_ai_search,
    get_external_similar_profiles_name_search,
    get_external_similar_profiles_groups,
    get_external_similar_profiles_rank,
    get_external_similar_profiles_function,
)
from app.utils.people.similar_profiles.regular.utilities import (
    get_all_active_experiences,
    drill_relative_experience,
    drill_relative_experience_fagr,
)
from app.utils.people.similar_profiles.regular.cache_utilities import (
    get_cache,
    set_cache,
    delete_cache,
)


async def fetch_updated_at_es(ids, client, size=1000):
    query = {
        "query": {"ids": {"values": ids}},
        "_source": ["updated_at"],
        "size": size,
    }
    index = os.environ.get("ES_PROFILES_INDEX", "profile")
    response = await client.search(index=index, body=query)

    if "hits" not in response or "hits" not in response["hits"]:
        raise ValueError("Invalid Elasticsearch response structure")

    updated_at_es = {}
    hits = response["hits"]["hits"]
    for hit in hits:
        _id = hit["_id"]
        updated_at_es[_id] = hit["_source"].get("updated_at", None)

    return updated_at_es


async def is_cache_valid(cached_data, base_profile_latest_updatedAt, client):
    try:
        similar_profiles, esid_updatedat = cached_data

        if not isinstance(similar_profiles, list) or not isinstance(
            esid_updatedat, list
        ):
            raise ValueError("Invalid cache data structure")

        cache_updatedAt_target = esid_updatedat[0]
        base_profile_cached_updatedAt = (
            list(cache_updatedAt_target.values())[0] if cache_updatedAt_target else None
        )

        if base_profile_latest_updatedAt == base_profile_cached_updatedAt:
            cached_data_item = (
                similar_profiles[0]
                if isinstance(similar_profiles, list)
                else similar_profiles
            )
            cached_updated_at_es = cached_data_item.get("updated_at")
            cached_profiles = cached_data_item.get("ids_with_experience")

            if cached_profiles and cached_updated_at_es:
                cached_es_ids = [item["esId"] for item in cached_profiles]

                current_updated_at_es = await fetch_updated_at_es(
                    cached_es_ids, client, size=1000
                )

                if all(
                    cached_updated_at_es.get(es_id) == current_updated_at_es.get(es_id)
                    for es_id in cached_es_ids
                ):
                    return True, cached_profiles
                else:
                    return False, None
            else:
                return False, None
        else:
            return False, None
    except Exception as e:
        traceback.print_exc()
        return False, None


async def get_similar_profiles_data(
    _id,
    type_,
    service_type,
    experience_indices,
    groups,
    rank,
    function,
    client,
    connector,
):
    if type_ == "external":
        if service_type == "ai_search":
            return await get_external_similar_profiles_ai_search(
                _id, experience_indices, client, connector, retries=1, delay=1
            )
        elif service_type == "name_search":
            return await get_external_similar_profiles_name_search(
                _id, experience_indices, client, connector, retries=1, delay=1
            )
        elif service_type == "similar_profiles":
            return await get_external_similar_profiles_ai_search(
                _id, experience_indices, client, connector, retries=1, delay=1
            )
        elif service_type == "groups":
            return await get_external_similar_profiles_groups(
                _id, experience_indices, client, connector, groups, retries=1, delay=1
            )
        elif service_type == "rank":
            return await get_external_similar_profiles_rank(
                _id, experience_indices, client, connector, rank, retries=1, delay=1
            )
        elif service_type == "function":
            return await get_external_similar_profiles_function(
                _id, experience_indices, client, connector, function, retries=1, delay=1
            )
    elif type_ == "internal":
        if service_type == "ai_search":
            return await get_internal_similar_profiles_ai_search(
                _id, experience_indices, client, connector, retries=1, delay=1
            )
        elif service_type == "name_search":
            return await get_internal_similar_profiles_name_search(
                _id, experience_indices, client, connector, retries=1, delay=1
            )
        elif service_type == "similar_profiles":
            return await get_internal_similar_profiles_ai_search(
                _id, experience_indices, client, connector, retries=1, delay=1
            )
        elif service_type == "groups":
            return await get_internal_similar_profiles_groups(
                _id, experience_indices, client, connector, groups, retries=1, delay=1
            )
        elif service_type == "rank":
            return await get_internal_similar_profiles_rank(
                _id, experience_indices, client, connector, rank, retries=1, delay=1
            )
        elif service_type == "function":
            return await get_internal_similar_profiles_function(
                _id, experience_indices, client, connector, function, retries=1, delay=1
            )


async def similar_profiles(payload, client, connector):
    _id = payload.esId
    type_ = payload.type
    offset = payload.offset
    limit = payload.limit
    service_type = payload.serviceType
    experience_indices = payload.experienceIndices or []
    groups = payload.groups
    rank = payload.rank
    function = payload.function
    filters = payload.filters
    peopleFilters = payload.peopleFilters

    if not isinstance(filters, dict):
        try:
            filters = json.loads(filters)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid filters format")

    if None in experience_indices:
        raise HTTPException(status_code=400, detail="Bad Input")

    if service_type in {"name_search", "ai_search"}:
        if len(experience_indices) == 0:
            active_experiences = await get_all_active_experiences(_id, client)
            active_indices = [item["index"] for item in active_experiences]
            experience_indices = (
                await drill_relative_experience(active_experiences)
                if len(active_indices) > 1
                else active_indices
            )

    elif service_type in {"groups", "rank", "function"}:
        if len(experience_indices) == 0:
            active_experiences = await get_all_active_experiences(_id, client)
            active_indices = [item["index"] for item in active_experiences]
            experience_indices = (
                await drill_relative_experience_fagr(active_experiences, peopleFilters)
                if len(active_indices) > 1
                else active_indices
            )

    elif service_type in {"similar_profiles"}:
        experience_indices = experience_indices

    input_profile_updated_at = await fetch_updated_at_es([_id], client, size=1)
    base_profile_latest_updatedAt = (
        list(input_profile_updated_at.values())[0] if input_profile_updated_at else None
    )

    cached_data = await get_cache(
        es_id=_id,
        type=type_,
        service_type=service_type,
        experience_indices=experience_indices,
        groups=groups,
        rank=rank,
        function=function,
    )

    if cached_data:
        cache_valid, cached_profiles = await is_cache_valid(
            cached_data, base_profile_latest_updatedAt, client
        )
        if cache_valid:
            start_index = offset
            end_index = start_index + limit
            return cached_profiles[start_index:end_index], len(cached_profiles)
        else:
            await delete_cache(
                es_id=_id,
                type=type_,
                service_type=service_type,
                experience_indices=experience_indices,
                groups=groups,
            )

    ids_with_experience = await get_similar_profiles_data(
        _id,
        type_,
        service_type,
        experience_indices,
        groups,
        rank,
        function,
        client,
        connector,
    )

    if not ids_with_experience:
        return {"message": "Not Found"}

    es_ids = [item["esId"] for item in ids_with_experience if item and item.get("esId")]
    updated_at_es = await fetch_updated_at_es(es_ids, client, size=1000)

    try:
        asyncio.create_task(
            set_cache(
                es_id=_id,
                type=type_,
                service_type=service_type,
                groups=groups,
                rank=rank,
                function=function,
                experience_indices=experience_indices,
                similar_profiles=[
                    {
                        "ids_with_experience": ids_with_experience,
                        "updated_at": updated_at_es,
                    }
                ],
                esId_updatedAt=input_profile_updated_at,
                expiration=datetime.datetime.now() + datetime.timedelta(days=7),
            )
        )
    except Exception as e:
        print(e)
        traceback.print_exc()

    start_index = offset
    end_index = start_index + limit
    return ids_with_experience[start_index:end_index], len(ids_with_experience)
