import json
import asyncio
from app.utils.people.similar_profiles.regular.utilities import (
    get_data,
    get_company_universalname_by_urn,
    get_linkedin_identifier,
    get_company_location,
    normalize_title,
    get_location_data,
    get_experience_status,
)
from app.utils.people.similar_profiles.regular.query import execute_query


async def process_experience_index(
    _id, experience_index, client, connector, groups=None, rank=None, function=None
):

    try:

        results = await asyncio.gather(
            get_data(_id, experience_index, connector), get_location_data(_id, client)
        )

        (
            (universal_name, company_name, company_urn, profile_data),
            location_data,
        ) = results

        if not universal_name:
            if company_urn:
                universal_name = await get_company_universalname_by_urn(
                    company_urn, client
                )
            elif company_name:
                universal_name = await get_linkedin_identifier(
                    company_name, None, client, None
                )
            else:
                return {}

        if not universal_name:
            return {}

        if not location_data or all(not v for v in location_data.values()):
            location_data = await get_company_location(universal_name, client)

        if isinstance(profile_data, str):
            try:
                profile_data_dict = json.loads(profile_data)
            except json.JSONDecodeError:
                profile_data_dict = {}
        else:
            profile_data_dict = profile_data

        company = (universal_name, 1)

        internal_competitors = {company: []}
        competitors_dict = {**internal_competitors}

        title = profile_data_dict.get("title", "Title not found")
        headline = profile_data_dict.get("headline", None)
        description = profile_data_dict.get("description", None)
        about = profile_data_dict.get("summary", None)

        normalized_titles, filter_type = await asyncio.gather(
            normalize_title(
                title, description, headline, about, service_flag="internal"
            ),
            get_experience_status(_id, experience_index, client),
        )

        esIds_indexes, sorted_titles = await execute_query(
            normalized_titles,
            competitors_dict,
            location_data,
            client,
            filter_type,
            title,
            service_flag="internal",
        )

        if _id in esIds_indexes:
            esIds_indexes.pop(_id)

        verified_esIds_list = [
            {"esId": es_id, "experienceIndex": index}
            for es_id, index in esIds_indexes.items()
        ]

        return verified_esIds_list

    except Exception as e:
        print(f"Exception in processing experience index {experience_index}: {e}")
        return []


async def get_internal_similar_profiles_ai_search(
    _id, experience_indices, client, connector, retries, delay
):
    for attempt in range(retries):
        try:
            tasks = [
                process_experience_index(_id, idx, client, connector)
                for idx in experience_indices
            ]
            results = await asyncio.gather(*tasks)
            combined_results = [
                res for sublist in results if sublist for res in sublist
            ]

            if combined_results:
                return combined_results
            else:
                print(f"Attempt {attempt + 1} failed: combined_results is empty")

        except Exception as e:
            print(f"Attempt {attempt + 1} failed due to exception: {e}")

        if attempt < retries - 1:
            await asyncio.sleep(delay)

    return {}


async def get_internal_similar_profiles_name_search(
    _id, experience_indices, client, connector, retries, delay
):
    for attempt in range(retries):
        try:
            tasks = [
                process_experience_index(_id, idx, client, connector)
                for idx in experience_indices
            ]
            results = await asyncio.gather(*tasks)
            combined_results = [
                res for sublist in results if sublist for res in sublist
            ]

            if combined_results:
                return combined_results
            else:
                print(f"Attempt {attempt + 1} failed: combined_results is empty")

        except Exception as e:
            print(f"Attempt {attempt + 1} failed due to exception: {e}")

        if attempt < retries - 1:
            await asyncio.sleep(delay)

    return {}


async def get_internal_similar_profiles_groups(
    _id, experience_indices, client, connector, groups, retries, delay
):
    for attempt in range(retries):
        try:
            tasks = [
                process_experience_index(
                    _id,
                    idx,
                    client,
                    connector,
                    groups=groups,
                    rank=None,
                    function=None,
                )
                for idx in experience_indices
            ]
            results = await asyncio.gather(*tasks)
            combined_results = [
                res for sublist in results if sublist for res in sublist
            ]

            if combined_results:
                return combined_results
            else:
                print(f"Attempt {attempt + 1} failed: combined_results is empty")

        except Exception as e:
            print(f"Attempt {attempt + 1} failed due to exception: {e}")

        if attempt < retries - 1:
            await asyncio.sleep(delay)

    return {}


async def get_internal_similar_profiles_rank(
    _id, experience_indices, client, connector, rank, retries, delay
):
    for attempt in range(retries):
        try:
            tasks = [
                process_experience_index(
                    _id,
                    idx,
                    client,
                    connector,
                    groups=None,
                    rank=rank,
                    function=None,
                )
                for idx in experience_indices
            ]
            results = await asyncio.gather(*tasks)
            combined_results = [
                res for sublist in results if sublist for res in sublist
            ]

            if combined_results:
                return combined_results
            else:
                print(f"Attempt {attempt + 1} failed: combined_results is empty")

        except Exception as e:
            print(f"Attempt {attempt + 1} failed due to exception: {e}")

        if attempt < retries - 1:
            await asyncio.sleep(delay)

    return {}


async def get_internal_similar_profiles_function(
    _id, experience_indices, client, connector, function, retries, delay
):
    for attempt in range(retries):
        try:
            tasks = [
                process_experience_index(
                    _id,
                    idx,
                    client,
                    connector,
                    groups=None,
                    rank=None,
                    function=function,
                )
                for idx in experience_indices
            ]
            results = await asyncio.gather(*tasks)
            combined_results = [
                res for sublist in results if sublist for res in sublist
            ]

            if combined_results:
                return combined_results
            else:
                print(f"Attempt {attempt + 1} failed: combined_results is empty")

        except Exception as e:
            print(f"Attempt {attempt + 1} failed due to exception: {e}")

        if attempt < retries - 1:
            await asyncio.sleep(delay)

    return {}
