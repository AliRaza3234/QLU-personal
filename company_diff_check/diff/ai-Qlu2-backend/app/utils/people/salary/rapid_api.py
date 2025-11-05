import os
import aiohttp
import random
from app.core.database import get_cached_data, cache_data


title_cache = "~salary~rapidapi~time@"
table = "cache_salary_rapidApi"

from datetime import datetime

from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync

token = os.getenv("TOKEN")
org = os.getenv("SITE")
url = os.getenv("URL")

__client = None


async def make_influxdb_connection():
    global __client
    if not __client:
        __client = InfluxDBClientAsync(
            url=url, token=token, org=org, enable_gzip=False, timeout=1000000
        )
    try:
        if await __client.ping():
            return __client
    except Exception as e:
        __client = InfluxDBClientAsync(
            url=url, token=token, org=org, enable_gzip=False, timeout=1000000
        )
        print("Exception: ", e)
    return __client


async def run_influx_query(query):
    try:
        client = await make_influxdb_connection()
        result = await client.query_api().query(query)
        return result
    except Exception as e:
        print(e)


mapping_1 = {
    "Less than $1M": 12.5,
    "$1M to $10M": 25,
    "$10M to $50M": 37.5,
    "$50M to $100M": 50,
    "$100M to $500M": 62.5,
    "$500M to $1B": 75,
    "$1B to $10B": 87.5,
    "$10B+": 100,
}

list_1 = [
    "Less than $1M",
    "$1M to $10M",
    "$10M to $50M",
    "$50M to $100M",
    "$100M to $500M",
    "$500M to $1B",
    "$1B to $10B",
    "$10B+",
]

list_2 = [500, 4000, 10000, 20000, 50000, 100000, "100k+"]
mapping_2 = {
    500: 100,
    4000: 83,
    10000: 66,
    20000: 50,
    50000: 33,
    100000: 20,
    "100k+": 12,
}


# final = {
#     "title": "",
#     "min": None,
#     "max": None,
#     "average": None,
#     "Calculated Considering Company": None,
#     "source": ""
#  }


async def Title_Country_Salary(company, session, title, location, radius):
    async with session.get(
        f"https://job-salary-data.p.rapidapi.com/job-salary?job_title={company} {title}&location={location} glassdoor&radius={radius}",
        headers={
            "X-RapidAPI-Key": os.getenv("RAPID_KEY"),
            "X-RapidAPI-Host": "job-salary-data.p.rapidapi.com",
        },
    ) as response:
        if response.status == 200:
            data = await response.json()
            if data["status"] == "OK":
                if "data" in data:
                    if data["data"]:
                        return data["data"]
                else:
                    pass

    async with session.get(
        f"https://job-salary-data.p.rapidapi.com/job-salary?job_title={title}&location={location} glassdoor&radius={radius}",
        headers={
            "X-RapidAPI-Key": os.getenv("RAPID_KEY"),
            "X-RapidAPI-Host": "job-salary-data.p.rapidapi.com",
        },
    ) as response:
        if response.status == 200:
            data = await response.json()
            if data["status"] == "OK":
                if "data" in data:
                    if data["data"]:
                        return data["data"]
                else:
                    pass

    async with session.get(
        f"https://job-salary-data.p.rapidapi.com/job-salary?job_title={title}&location={location}&radius={radius}",
        headers={
            "X-RapidAPI-Key": os.getenv("RAPID_KEY"),
            "X-RapidAPI-Host": "job-salary-data.p.rapidapi.com",
        },
    ) as response:
        if response.status == 200:
            data = await response.json()
            if data["status"] == "OK":
                if "data" in data:
                    if data["data"]:
                        return data["data"]
                else:
                    pass
    return None


async def Title_Country_Salary_P(company, session, title, location, radius):
    async with session.get(
        f"https://job-salary-data.p.rapidapi.com/job-salary?job_title={company} {title}&location={location}&radius={radius}",
        headers={
            "X-RapidAPI-Key": os.getenv("RAPID_KEY"),
            "X-RapidAPI-Host": "job-salary-data.p.rapidapi.com",
        },
    ) as response:
        if response.status == 200:
            data = await response.json()
            if data["status"] == "OK":
                if "data" in data:
                    if data["data"]:
                        return data["data"]
                else:
                    pass

    async with session.get(
        f"https://job-salary-data.p.rapidapi.com/job-salary?job_title={title}&location={location}&radius={radius}",
        headers={
            "X-RapidAPI-Key": os.getenv("RAPID_KEY"),
            "X-RapidAPI-Host": "job-salary-data.p.rapidapi.com",
        },
    ) as response:
        if response.status == 200:
            data = await response.json()
            if data["status"] == "OK":
                if "data" in data:
                    if data["data"]:
                        return data["data"]
                else:
                    pass

    return None


async def RapidApi(company, title, location, radius, background_task, es, CACHE=True):

    async with aiohttp.ClientSession() as session:
        if CACHE == True:
            try:
                cached_data = await get_cached_data(title + title_cache, table)
                if cached_data:
                    return cached_data  ###################################################################################
            except Exception as e:
                pass

        if "pakistan" in location.lower():
            results = await Title_Country_Salary_P(
                company, session, title, location, radius
            )
        else:
            results = await Title_Country_Salary(
                company, session, title, location, radius
            )
    if not results:
        return None

    final = {
        "title": "",
        "min": None,
        "max": None,
        "average": None,
        "Calculated Considering Company": None,
        "source": "",
    }

    sum = summax = summin = count = 0

    ran = random.randint(0, len(results) - 1)
    salary_url = results[ran]["publisher_link"]

    for i in results:
        try:
            if not i["median_salary"] or not i["max_salary"] or not i["min_salary"]:
                continue
        except:
            continue
        if results[0]["salary_currency"] != i["salary_currency"]:
            continue
        if i["salary_period"] == "MONTH":
            sum = sum + (i["median_salary"] * 12)  # Months in an year
            summax = summax + (i["max_salary"] * 12)
            summin = summin + (i["min_salary"] * 12)
        elif i["salary_period"] == "YEAR":
            sum = sum + i["median_salary"]
            summax = summax + (i["max_salary"])
            summin = summin + (i["min_salary"])
        elif "hour" in i["salary_period"].lower():
            sum = sum + (i["median_salary"] * 2080)  ## Working hours in an year
            summax = summax + (i["max_salary"] * 2080)
            summin = summin + (i["min_salary"] * 2080)
        elif "day" in i["salary_period"].lower():
            sum = sum + (i["median_salary"] * 260)  ## Working days in an year
            summax = summax + (i["max_salary"] * 260)
            summin = summin + (i["min_salary"] * 260)
        else:
            continue
        count = count + 1

    if sum == 0 or summin == 0 or summax == 0:
        return None

    AvgMedian = sum / count
    AvgMin = summin / count
    AvgMax = summax / count

    final["title"] = title
    final["min"] = AvgMin
    final["max"] = AvgMax
    final["average"] = AvgMedian
    final["Calculated Considering Company"] = None
    final["source"] = salary_url

    currency = results[0]["salary_currency"]

    api_key = (os.getenv("ES_ID"), os.getenv("ES_KEY"))
    es_host = os.getenv("ES_URL")
    # es = AsyncElasticsearch(
    #     hosts=es_host,
    #     api_key=api_key,
    #     request_timeout=7,
    #     max_retries=3,
    #     retry_on_timeout=True,
    # )

    if not company:
        return final

    query = {
        "size": 1,
        "_source": ["li_staffcount", "_id"],
        "query": {"term": {"li_universalname": {"value": company.lower()}}},
    }

    response = await es.search(body=query, index=os.getenv("ES_COMPANIES_INDEX"))

    staff = None
    try:
        staff = response["hits"]["hits"][0]["_source"]["li_staffcount"]
        elasticsearch_ID = response["hits"]["hits"][0]["_id"]
    except:
        staff = None
        elasticsearch_ID = None

    if not staff or staff == 0 or not elasticsearch_ID:
        if CACHE == True:
            background_task.add_task(cache_data, title + title_cache, final, table)
        return final

    current_utc = datetime.utcnow()

    formatted_time = current_utc.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    query_marketcap = f"""from(bucket: "revenue_production_bucket")
    |> range(start: 0, stop: {formatted_time})
    |> filter(fn: (r) => r.es_id == "{elasticsearch_ID}")
    |> filter(fn: (r) => r._measurement == "yearly_financial_growth")
    |> filter(fn: (r) => r._field == "revenue")"""

    result = await run_influx_query(query_marketcap)

    if not result:
        query_marketcap = f"""from(bucket: "estimated_revenue")
        |> range(start: 0, stop: {formatted_time})
        |> filter(fn: (r) => r.es_id == "1009441")
        |> filter(fn: (r) => r._measurement == "estimated_revenue")
        |> filter(fn: (r) => r._field == "revenue")
        """
        result = await run_influx_query(query_marketcap)

        if not result:
            if CACHE == True:
                background_task.add_task(cache_data, title + title_cache, final, table)
            return final

    total = []
    for j in result[0]:
        if j["_value"] < 1000000:
            total.append("Less than $1M")
        elif j["_value"] < 10000000:
            total.append("$1M to $10M")
        elif j["_value"] < 50000000:
            total.append("$10M to $50M")
        elif j["_value"] < 100000000:
            total.append("$50M to $100M")
        elif j["_value"] < 500000000:
            total.append("$100M to $500M")
        elif j["_value"] < 1000000000:
            total.append("$500M to $1B")
        else:
            total.append("$10B+")

    max = -1
    for i in total:
        if max < list_1.index(i):
            max = list_1.index(i)

    if max == -1:
        if CACHE == True:
            background_task.add_task(cache_data, title + title_cache, final, table)

        return final

    for i in list_2:
        try:
            if staff < i:
                variable = i
                break
        except:
            variable = i

    percentile = (
        (mapping_1[list(mapping_1.keys())[max]] + mapping_2[variable]) / 2
    ) / 100

    salary = AvgMin + ((AvgMax - AvgMin) * percentile)
    final["Calculated Considering Company"] = salary

    if CACHE == True:
        background_task.add_task(cache_data, title + title_cache, final, table)
    # print("FINAL: \n", final)
    return final
