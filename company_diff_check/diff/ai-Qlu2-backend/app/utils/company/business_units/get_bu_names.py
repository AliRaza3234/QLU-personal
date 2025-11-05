from app.core.database import postgres_fetch


async def busniess_units_names(universal_name):
    fetch_query = f"""
        SELECT revenue from bu_revenue_all where universal_name = '{universal_name}'
    """
    response = await postgres_fetch(fetch_query)

    if response == None:
        return None

    response = response[0]

    return_response = []

    for key in response:
        if (
            "revenuefrom" in key.lower()
            or "revenue from" in key.lower()
            or "unearned" in key.lower()
            or "other" in key.lower()
        ):
            pass
        else:
            return_response.append({key: []})

    return return_response
