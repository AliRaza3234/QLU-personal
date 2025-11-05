import json
import asyncio
import traceback
from app.utils.people.similar_profiles.regular.utilities import (
    get_data,
    filter_invalid_companies,
    get_linkedin_identifier,
    get_company_data,
    company_competitors,
    get_base_product,
    normalize_title,
    get_experience_status,
    get_location_data,
    get_company_sizes,
    industry_for_cache,
    get_company_location,
    get_company_universalname_by_urn,
)
from app.utils.people.similar_profiles.regular.query import execute_query
from app.utils.people.similar_profiles.regular.cache_utilities import (
    get_similar_companies,
    set_similar_companies,
    delete_similar_companies,
    check_cache_expiry,
)


async def get_or_compute_companies(
    profile_data_dict,
    company_name,
    company_data,
    universal_name,
    products,
    client,
):
    company_types = ["p2p_companies", "llm_companies", "companies_through_industry"]
    results = {}

    industry_cache = await industry_for_cache(profile_data_dict)

    for company_type in company_types:
        cached_data = await get_similar_companies(
            universal_name=universal_name,
            type=company_type,
            industry=industry_cache if industry_cache else None,
        )

        if cached_data and isinstance(cached_data[0], dict):
            results[company_type] = cached_data[0].get("similar_companies")
        elif cached_data and isinstance(cached_data[0], list):
            results[company_type] = cached_data[0][0].get("similar_companies")
        else:
            results[company_type] = None

    if all(value is None for value in results.values()):
        (
            p2p_companies,
            llm_companies,
            companies_through_industry,
        ) = await company_competitors(
            profile_data_dict,
            company_name,
            company_data,
            universal_name,
            products,
            client,
        )

        if llm_companies is not None:
            if results.get("p2p_companies") is None:
                filtered_p2p = filter_invalid_companies(p2p_companies)
                results["p2p_companies"] = filtered_p2p
                asyncio.create_task(
                    set_similar_companies(
                        universal_name,
                        "p2p_companies",
                        [{"similar_companies": filtered_p2p}],
                        industry_cache,
                    )
                )

            if results.get("llm_companies") is None:
                filtered_llm = filter_invalid_companies(llm_companies)
                results["llm_companies"] = filtered_llm
                asyncio.create_task(
                    set_similar_companies(
                        universal_name,
                        "llm_companies",
                        [{"similar_companies": filtered_llm}],
                        industry_cache,
                    )
                )

            if results.get("companies_through_industry") is None:
                filtered_industry = filter_invalid_companies(companies_through_industry)
                results["companies_through_industry"] = filtered_industry
                asyncio.create_task(
                    set_similar_companies(
                        universal_name,
                        "companies_through_industry",
                        [{"similar_companies": filtered_industry}],
                        industry_cache,
                    )
                )

    async def check_and_delete_cache():
        cache_is_old = await check_cache_expiry(universal_name, industry_cache)

        if cache_is_old:
            for company_type in company_types:
                asyncio.create_task(
                    delete_similar_companies(
                        universal_name=universal_name,
                        type=company_type,
                        industry=industry_cache,
                    )
                )

    asyncio.create_task(check_and_delete_cache())

    return (
        results["p2p_companies"],
        results["llm_companies"],
        results["companies_through_industry"],
    )


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

        if isinstance(profile_data, str):
            try:
                profile_data_dict = json.loads(profile_data)
            except json.JSONDecodeError:
                profile_data_dict = {}
        else:
            profile_data_dict = profile_data

        if groups:
            products = groups
        elif rank:
            products = await get_base_product(
                profile_data_dict.get("title", ""),
                profile_data_dict.get("description", ""),
                profile_data_dict.get("headline", ""),
                company_name,
            )
        elif function:
            products = await get_base_product(
                profile_data_dict.get("title", ""),
                profile_data_dict.get("description", ""),
                profile_data_dict.get("headline", ""),
                company_name,
            )
        else:
            products = await get_base_product(
                profile_data_dict.get("title", ""),
                profile_data_dict.get("description", ""),
                profile_data_dict.get("headline", ""),
                company_name,
            )
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

        # es_company_data, industry_cache = await asyncio.gather(
        #     get_company_data(universal_name, client),
        #     industry_for_cache(profile_data_dict),
        # )

        es_company_data = await get_company_data(universal_name, client)

        title = profile_data_dict.get("title", "Title not found")
        headline = profile_data_dict.get("headline", None)
        description = profile_data_dict.get("description", None)
        about = profile_data_dict.get("summary", None)

        if es_company_data:
            company_data = ", ".join(
                f"{label}: {es_company_data.get(key, company_name)}"
                for label, key in [
                    ("Company Name", None),
                    ("Company Description", "li_description"),
                    ("Company Industry", "li_industries"),
                    ("Company Size", "li_size"),
                ]
                if key is None or es_company_data.get(key)
            )
        else:
            company_data = ""

        (
            (p2p_companies, llm_companies, companies_through_industry),
            normalized_titles,
            filter_type,
        ) = await asyncio.gather(
            get_or_compute_companies(
                profile_data_dict,
                company_name,
                company_data,
                universal_name,
                products,
                client,
            ),
            normalize_title(
                title, description, headline, about, service_flag="external"
            ),
            get_experience_status(_id, experience_index, client),
        )

        p2p_companies = p2p_companies or {}
        llm_companies = llm_companies or {}
        companies_through_industry = companies_through_industry or []

        master_companies = (
            list(p2p_companies.keys())
            + list(llm_companies.keys())
            + companies_through_industry
            + [universal_name]
        )
        master_companies_keywords = list(p2p_companies.values())

        master_companies_sizes = await get_company_sizes(master_companies, client)

        base_company_size = master_companies_sizes.get(universal_name, 0)

        boosted_companies = {}

        for company, size_value in master_companies_sizes.items():
            if base_company_size >= 10000:
                if size_value > 10000:
                    boost = round(
                        6
                        + (
                            2
                            * (
                                1
                                - abs(size_value - base_company_size)
                                / base_company_size
                            )
                        ),
                        2,
                    )
                    boosted_companies[company] = min(max(boost, 6), 8)
                elif 5001 <= size_value <= 10000:
                    boost = round(
                        4
                        + (
                            2
                            * (
                                1
                                - abs(size_value - base_company_size)
                                / base_company_size
                            )
                        ),
                        2,
                    )
                    boosted_companies[company] = min(max(boost, 4), 6)

            elif 5001 <= base_company_size < 10000:
                if 5001 <= size_value <= 10000:
                    boosted_companies[company] = 6
                elif size_value > 10000:
                    boosted_companies[company] = 4
                elif 501 <= size_value <= 5000:
                    boosted_companies[company] = 2

            elif 501 <= base_company_size <= 5000:
                if base_company_size > 2000:
                    if 501 <= size_value <= 5000:
                        boosted_companies[company] = 2
                    elif 5001 <= size_value <= 10000:
                        boosted_companies[company] = 6
                    elif size_value > 10000:
                        boosted_companies[company] = 4
                else:
                    if 501 <= size_value <= 5000:
                        boosted_companies[company] = 4
                    elif 5001 <= size_value <= 10000:
                        boosted_companies[company] = 6
                    elif size_value > 10000:
                        boosted_companies[company] = 2

            elif 0 < base_company_size <= 500:
                if 0 < size_value <= 500:
                    boosted_companies[company] = 6
                elif 501 <= size_value <= 5000:
                    boosted_companies[company] = 4

            else:
                if size_value > 50000:
                    boosted_companies[company] = 1
                elif 10001 <= size_value <= 50000:
                    boosted_companies[company] = 1
                elif 1001 <= size_value <= 10000:
                    boosted_companies[company] = 1
                elif 101 <= size_value <= 1000:
                    boosted_companies[company] = 1
                else:
                    boosted_companies[company] = 1

        del boosted_companies[universal_name]

        converted_data = {}

        iterator = 0
        for company, score in boosted_companies.items():
            if len(master_companies_keywords) > iterator:
                converted_data[(company, score)] = master_companies_keywords[iterator]
            else:
                converted_data[(company, score)] = []
            iterator += 1

        esIds_indexes_industry, sorted_titles_industry = await execute_query(
            normalized_titles,
            converted_data,
            location_data,
            client,
            filter_type,
            title,
            service_flag="external",
        )

        esIds_indexes = esIds_indexes_industry

        if _id in esIds_indexes:
            esIds_indexes.pop(_id)

        verified_esIds_list = [
            {"esId": es_id, "experienceIndex": index}
            for es_id, index in esIds_indexes.items()
        ]

        return verified_esIds_list

    except Exception as e:
        print(f"Exception in processing experience index {experience_index}: {e}")
        traceback.print_exc()
        return []


async def get_external_similar_profiles_ai_search(
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


async def get_external_similar_profiles_name_search(
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


async def get_external_similar_profiles_groups(
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


async def get_external_similar_profiles_rank(
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


async def get_external_similar_profiles_function(
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
