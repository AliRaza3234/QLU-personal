from app.core.database import postgres_fetch


def get_bu_revenue(response_dict, bu):
    bu_revenue = {bu: {}}

    bu_response = response_dict[bu]

    quarters = ["1", "2", "3", "4"]

    year_dict = {}

    for year, revenue in bu_response.items():
        quarter_dict = {}

        for quarter in quarters:
            if quarter in revenue.keys():
                quarter_dict[quarter] = revenue[quarter]
            else:
                quarter_dict[quarter] = None

        year_dict[year] = quarter_dict

    bu_revenue[bu] = year_dict

    return bu_revenue


async def bu_revenue_quarter(universal_name, bu):
    fetch_query = f"""
        SELECT revenue from bu_revenue_all where universal_name = '{universal_name}'
    """

    response = await postgres_fetch(fetch_query)

    if response == None:
        return None

    response = response[0]

    bu_revenue = get_bu_revenue(response, bu)

    return bu_revenue
