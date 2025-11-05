from app.core.database import postgres_fetch


async def groups_to_revenue(universal_name):
    fetch_query = f"""
        SELECT * from group_revenues where universal_name = '{universal_name}'
    """

    response = await postgres_fetch(fetch_query)
    return response
