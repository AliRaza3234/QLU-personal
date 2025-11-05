import ast
import asyncio
from app.utils.company.competitors.utilities import (
    company_fullname,
    company_location,
    get_company_data,
    get_company_status,
    get_competitor,
    get_competitor_unpopular,
    filter_competitors_by_size,
    determine_company_size,
)
from app.core.database import cache_data, get_cached_data
from app.utils.search.aisearch.company.generation.mapping import map_company


async def generate_competitor(universalname, client, mysql_pool, redis_client):
    company_name, company_size, company_loc, es_company_data = await asyncio.gather(
        company_fullname(universalname, client),
        determine_company_size(universalname, client),
        company_location(universalname, client),
        get_company_data(universalname, client),
    )

    if not company_name:
        return []

    cached_response = await get_cached_data(universalname, "cache_company_competitors")

    if cached_response:
        return cached_response

    company_status_str = await get_company_status(company_name)
    company_status = company_status_str == "True"

    if company_status == True:
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
                ("Company Sub-Industry", "li_subindustry"),
            ]
            if key is None or key in es_company_data and es_company_data[key]
        )
        external_competitors_data = await get_competitor(
            company_name, es_company_data, company_size
        )

    elif company_status == False:

        if company_loc is None:
            company_loc = "United States"

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
                ("Company Sub-Industry", "li_subindustry"),
            ]
            if key is None or key in es_company_data and es_company_data[key]
        )

        external_competitors_data = await get_competitor_unpopular(
            company_name, company_data, company_size, company_loc
        )

    try:
        external_competitors_data = ast.literal_eval(external_competitors_data)
    except (ValueError, SyntaxError) as e:
        print("Error evaluating the response as a Python list:", e)
        return None

    unique_string_list = []
    seen = set()

    for string in external_competitors_data:
        if string not in seen:
            unique_string_list.append(string)
            seen.add(string)
    external_competitors_data = unique_string_list

    tasks = []
    for company in external_competitors_data:
        tasks.append(
            map_company(company, company_name, [], client, mysql_pool, redis_client)
        )

    results = await asyncio.gather(*tasks)

    final_output = []
    for r in results:
        try:
            final_output.append(r[1]["li_universalname"])
        except:
            pass

    if isinstance(final_output, str):
        try:
            final_output = ast.literal_eval(final_output)
        except (SyntaxError, ValueError) as e:
            raise ValueError("final_output is not a valid list format.") from e

    competitors_with_sizes = []
    batch_size = 5
    for i in range(0, len(final_output), batch_size):
        batch = final_output[i : i + batch_size]
        size_results = await asyncio.gather(
            *[determine_company_size(competitor, client) for competitor in batch]
        )
        competitors_with_sizes.extend(
            (competitor, size) for competitor, size in zip(batch, size_results) if size
        )

    final_output_filtered = filter_competitors_by_size(
        company_size, competitors_with_sizes
    )

    for competitor, size in competitors_with_sizes:
        if size is None and competitor not in final_output_filtered:
            final_output_filtered.append(competitor)

    if universalname in final_output_filtered:
        final_output_filtered.remove(universalname)

    if final_output_filtered:
        await cache_data(
            universalname,
            final_output_filtered,
            "cache_company_competitors",
            expiration_days=30,
        )

    return final_output_filtered
