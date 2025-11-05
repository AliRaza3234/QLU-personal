from app.utils.people.gfr.utilities import get_profiles_by_function


async def get_functions_profiles(payload, client):

    universal_name = payload["universal_name"]
    function = payload["function"]
    limit = payload["limit"]
    offset = payload["offset"]

    es_ids = await get_profiles_by_function(
        universal_name, function, client, limit=limit, offset=offset
    )

    return es_ids
