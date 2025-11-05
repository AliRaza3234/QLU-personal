import json
import asyncio
from .utilities import (
    get_linkedin_identifier,
    get_data,
    filter_dict_by_value_range,
    normalize_title,
    similar_regions,
    validator_agent,
    function_keywords,
)
from app.utils.people.similar_profiles.extension.query import execute_query


async def get_internal_similar_profiles(_id, client, connector, retries=3, delay=1):
    for attempt in range(retries):
        try:
            universal_name, company_name, profile_data = await get_data(_id, connector)

            if not universal_name:
                universal_name = await get_linkedin_identifier(company_name)

            if not universal_name:
                return {
                    "status": "universal_name not found",
                    "message": "Client Closed",
                }

            if isinstance(profile_data, str):
                try:
                    profile_data_dict = json.loads(profile_data)
                except json.JSONDecodeError:
                    print("Invalid JSON string")
                    profile_data_dict = {}
            else:
                profile_data_dict = profile_data

            country = profile_data_dict.get("country")
            if country is None:
                country = "United States"

            if isinstance(profile_data_dict, dict):
                title = profile_data_dict.get("title", "Title not found")
            else:
                print("Profile data is not a valid dictionary.")

            keywords_profile, normalized_titles_raw, countries = await asyncio.gather(
                function_keywords(
                    profile_data_dict["title"],
                    profile_data_dict["headline"],
                    profile_data_dict["description"],
                ),
                normalize_title(title),
                similar_regions(country, universal_name),
            )

            Core = keywords_profile.get("core", [])
            Secondary = keywords_profile.get("secondary", [])

            normalized_titles = normalized_titles_raw
            normalized_titles.append(title)

            internal_competitors = {universal_name: []}
            competitors_dict = {**internal_competitors}

            esIds_indexes, sorted_titles = await execute_query(
                normalized_titles,
                competitors_dict,
                (Core, Secondary),
                countries,
                client,
            )

            if _id in sorted_titles:
                del sorted_titles[_id]

            verified_ids = []

            tasks = []
            tasks.append(validator_agent(title))
            for value in sorted_titles.values():
                tasks.append(validator_agent(value))
            scores = await asyncio.gather(*tasks)

            title_score = scores[0]
            scores = scores[1:]

            titles_dict = {}
            iterator = 0
            for id, title in sorted_titles.items():
                titles_dict[id] = scores[iterator]
                iterator += 1

            titles_dict = filter_dict_by_value_range(titles_dict, title_score)

            verified_ids = list(titles_dict.keys())

            verified_esIds_indexes = {
                es_id: index
                for es_id, index in esIds_indexes.items()
                if es_id in verified_ids
            }

            verified_esIds_list = [
                {"esId": es_id, "experienceIndex": index}
                for es_id, index in verified_esIds_indexes.items()
            ]

            if verified_esIds_list:
                return verified_esIds_list
            else:
                print(f"Attempt {attempt + 1} failed: verified_esIds_list is empty")

        except Exception as e:
            print(f"Attempt {attempt + 1} failed due to exception: {e}")

        if attempt < retries - 1:
            await asyncio.sleep(delay)

    return {}
