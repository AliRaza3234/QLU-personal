import os, httpx


async def get_profile_counts(payload):
    if payload is None:
        return {"count": -1}
    url = os.getenv("PROFILE_COUNTS", None)
    headers = {
        "Content-Type": "application/json",
        "Authorization": os.getenv("FS_AUTHORIZATION"),
    }
    async with httpx.AsyncClient(timeout=40) as client:
        response = await client.post(url, json=payload, headers=headers)
        return response.json()


async def get_profile_suggestions(payload):
    url = os.getenv("PROFILE_SUGGESTIONS", None)
    headers = {
        "Content-Type": "application/json",
        "Authorization": os.getenv("FS_AUTHORIZATION"),
    }
    async with httpx.AsyncClient(timeout=40) as client:
        response = await client.post(url, json=payload, headers=headers)
        return response.json()


async def ingest_profile_by_search_term(string_term):
    url = os.getenv("PROFILE_INGESTION_SEARCH_TERM")
    headers = {
        "Content-Type": "application/json",
        "Authorization": os.getenv("FS_AUTHORIZATION"),
    }
    payload = {"searchTerm": string_term}

    try:
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.post(url, json=payload, headers=headers)
            return response.json()
    except:
        return {}


async def ingest_profiles_identifier(data):
    url = os.getenv("PROFILE_INGESTION_IDENTIFIERS")
    headers = {
        "Content-Type": "application/json",
        "Authorization": os.getenv("FS_AUTHORIZATION"),
    }
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.post(url, headers=headers, json=data)
            response.raise_for_status()
            return response.json()
    except:
        return {}


async def map_locations_by_name(data):
    flag = False
    for i in data:
        if i:
            flag = True
            break

    if not flag:
        return {}

    url = os.getenv("MAP_LOCATIONS_URL", None)
    headers = {
        "Content-Type": "application/json",
        "Authorization": os.getenv("FS_AUTHORIZATION"),
    }

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(url, json=data, headers=headers)
        return response.json()
