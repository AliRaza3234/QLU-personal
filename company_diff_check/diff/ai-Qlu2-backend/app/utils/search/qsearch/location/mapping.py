from app.utils.search.qsearch.location.time_zones import time_zones
from app.utils.search.qsearch.location.regions import regions_with_country
from app.core.database import postgres_fetch


async def location_mapping(client, locality="", locationName=""):
    if locality and locationName:
        locality = locality.replace(f", {locationName}", "").strip()
        location_full_path = f"{locality}, {locationName}"
    elif locality and not locationName:
        location_full_path = locality
    elif not locality and locationName:
        location_full_path = locationName
    else:
        return {}
    query_location_full_path = f"select full_path  from location_full_path where partial_path='{location_full_path}';"
    new_location_full_path = await postgres_fetch(query_location_full_path)
    if new_location_full_path is None:
        new_location_full_path = location_full_path
    else:
        new_location_full_path = new_location_full_path[0]
    country = location_full_path.split(",")[-1].lower().strip()
    time_zone = None
    metro_areas = None
    try:
        if country == "united states":
            locations = location_full_path.split(",")
            for location in locations:
                if time_zone is None:
                    time_zone = time_zones.get(location.strip().lower(), None)
                if metro_areas is None:
                    query_metro_area = f"SELECT metro_areas from locations_data where country='united states' and name='{location.strip().lower()}' and metro_areas is not null"
                    result = await postgres_fetch(query_metro_area)
                    if result is not None:
                        metro_areas = " | ".join(result[0])
                    else:
                        search_metro_state = (
                            locality.lower().replace("united states", "").strip()
                        )

                        try:

                            query = {
                                "query": {
                                    "match_phrase": {
                                        "metropolitan_area": search_metro_state
                                    }
                                }
                            }

                            response = client.search(
                                body=query, index="metropolitan_areas_states"
                            )
                            metro_areas = response["hits"]["hits"][0]["_source"][
                                "metropolitan_area"
                            ]

                        except Exception as elastic_search_error:
                            pass

        query_cotinent = f"SELECT continents from countries where country='{country}'"
        result = await postgres_fetch(query_cotinent)
        continents = None

        if result is not None:
            result = [word.capitalize() for word in result[0]]
            continents = " | ".join(result)
    except Exception as e:
        print(e)
        return {}
    response = {}
    if metro_areas is not None:
        response["metro_areas"] = metro_areas
    if time_zone is not None:
        response["time_zone"] = time_zone
    if continents is not None:
        response["location_continent"] = continents
    response["locationFullPath"] = new_location_full_path

    try:
        regions = regions_with_country.get(country, None)
        response["location_continent"] += " | " + regions
    except Exception as e:
        print(e)

    return response
