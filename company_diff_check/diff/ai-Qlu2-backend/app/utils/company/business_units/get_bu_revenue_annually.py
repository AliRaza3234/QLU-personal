from app.core.database import postgres_fetch


def get_transformed_revenue(response_dict, bu):

    bu_revenue = {bu: {}}

    bu_response = response_dict[bu]

    year_dict = {}
    for year, revenue in bu_response.items():
        if "0" in revenue.keys():
            year_dict[year] = revenue["0"]
        else:
            year_dict[year] = None

    bu_revenue[bu] = year_dict

    return bu_revenue


async def bu_revenue_annual(universal_name, bu):
    fetch_query = f"""
        SELECT revenue from bu_revenue_all where universal_name = '{universal_name}'
    """

    response = await postgres_fetch(fetch_query)

    if response == None:
        return None

    response = response[0]

    bu_revenue = get_transformed_revenue(response, bu)

    return bu_revenue
