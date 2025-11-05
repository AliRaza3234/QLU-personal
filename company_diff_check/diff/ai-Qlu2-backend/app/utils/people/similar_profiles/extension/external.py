import json
import asyncio
from app.utils.people.similar_profiles.extension.utilities import (
    get_data,
    get_linkedin_identifier,
    get_company_data,
    company_competitors,
    filter_dict_by_value_range,
    get_base_product,
    function_keywords,
    normalize_title,
    similar_regions,
    validator_agent,
)
from app.utils.people.similar_profiles.extension.query import execute_query


async def get_external_similar_profiles(_id, client, connector, retries=3, delay=1):
    for attempt in range(retries):
        try:
            universal_name, company_name, profile_data = await get_data(_id, connector)

            if isinstance(profile_data, str):
                try:
                    profile_data_dict = json.loads(profile_data)
                except json.JSONDecodeError:
                    print("Invalid JSON string")
                    profile_data_dict = {}
            else:
                profile_data_dict = profile_data

            products = await get_base_product(
                profile_data_dict["title"],
                profile_data_dict["description"],
                profile_data_dict["headline"],
                company_name,
            )

            if not universal_name:
                if company_name:
                    universal_name = await get_linkedin_identifier(company_name)
                else:
                    return {"status": "universal_name and company_name not found"}

            if not universal_name:
                return {"status": "universal_name not found"}

            es_company_data = await get_company_data(universal_name, client)

            country = profile_data_dict.get("country")
            if country is None:
                country = "United States"

            if isinstance(profile_data_dict, dict):
                title = profile_data_dict.get("title", "Title not found")
            else:
                print("Profile data is not a valid dictionary.")

            if es_company_data:
                company_data = ", ".join(
                    (
                        f"{label}: {es_company_data[key]}"
                        if key in es_company_data
                        else f"{label}: {company_name}"
                    )
                    for label, key in [
                        ("Company Name", None),
                        ("Company Description", "li_description"),
                        ("Company Industry", "li_industries"),
                        ("Company Size", "li_size"),
                    ]
                    if key is None or key in es_company_data and es_company_data[key]
                )
            else:
                company_data = ""

            (
                keywords_profile,
                competitors_dict,
                normalized_titles,
                countries,
            ) = await asyncio.gather(
                function_keywords(
                    profile_data_dict["title"],
                    profile_data_dict["headline"],
                    profile_data_dict["description"],
                ),
                company_competitors(
                    profile_data,
                    company_name,
                    company_data,
                    universal_name,
                    products,
                    client,
                ),
                normalize_title(title),
                similar_regions(country, universal_name),
            )

            Core = keywords_profile.get("core", [])
            Secondary = keywords_profile.get("secondary", [])

            titles_to_exclude = ["CDO", "CSO"]
            normalized_titles = [
                title for title in normalized_titles if title not in titles_to_exclude
            ]

            normalized_titles.append(title)

            esIds_indexes, sorted_titles = await execute_query(
                normalized_titles,
                competitors_dict,
                (Core, Secondary),
                countries,
                client,
            )

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
