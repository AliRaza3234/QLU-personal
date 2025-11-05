from app.utils.people.gfr.utilities import ranking_data, get_ranked_esIds


async def rank_profiles(payload, client):
    universal_name = payload["universal_name"]
    offset = payload["offset"]
    limit = payload["limit"]
    rank = payload["rank"]

    ids = await get_ranked_esIds(
        ranking_data, rank, universal_name, client, limit=limit, offset=offset
    )
    return ids
