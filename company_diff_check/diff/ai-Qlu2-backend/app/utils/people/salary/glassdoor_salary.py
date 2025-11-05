import httpx
import random
from app.core.database import get_cached_data, cache_data
import re
import os

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


Countries_Ids = {
    "United States": 1,
    "United Kingdom": 2,
    "Canada": 3,
    "Aruba": 4,
    "Antigua and Barbuda": 5,
    "United Arab Emirates": 6,
    "Afghanistan": 7,
    "Algeria": 8,
    "Azerbaijan": 9,
    "Albania": 10,
    "Armenia": 11,
    "Andorra": 12,
    "Angola": 13,
    "American Samoa": 14,
    "Argentina": 15,
    "Australia": 16,
    "Ashmore and Cartier Islands": 17,
    "Austria": 18,
    "Anguilla": 19,
    "Antarctica": 20,
    "Bahrain": 21,
    "Barbados": 22,
    "Botswana": 23,
    "Bermuda": 24,
    "Belgium": 25,
    "Bahamas": 26,
    "Bangladesh": 27,
    "Belize": 28,
    "Bosnia and Herzegovina": 29,
    "Bolivia": 30,
    "Burma": 31,
    "Benin": 32,
    "Belarus": 33,
    "Solomon Islands": 34,
    "Navassa Island": 35,
    "Brazil": 36,
    "Bassas da India": 37,
    "Bhutan": 38,
    "Bulgaria": 39,
    "Bouvet Island": 40,
    "Brunei": 41,
    "Burundi": 42,
    "Cambodia": 43,
    "Chad": 44,
    "Sri Lanka": 45,
    "Republic of Congo": 46,
    "Democratic Republic of Congo": 47,
    "China": 48,
    "Chile": 49,
    "Cayman Islands": 50,
    "Cocos (Keeling) Islands": 51,
    "Cameroon": 52,
    "Comoros": 53,
    "Colombia": 54,
    "Northern Mariana Islands": 55,
    "Coral Sea Islands": 56,
    "Costa Rica": 57,
    "Central African Republic": 58,
    "Cuba": 59,
    "Cape Verde": 60,
    "Cook Islands": 61,
    "Cyprus": 62,
    "Denmark": 63,
    "Djibouti": 64,
    "Dominica": 65,
    "Jarvis Island": 66,
    "Dominican Republic": 67,
    "Ecuador": 68,
    "Egypt": 69,
    "Ireland": 70,
    "Equatorial Guinea": 71,
    "Estonia": 72,
    "Eritrea": 73,
    "El Salvador": 74,
    "Ethiopia": 75,
    "Europa Island": 76,
    "Czech Republic": 77,
    "French Guiana": 78,
    "Finland": 79,
    "Fiji": 80,
    "Falkland Islands (Islas Malvinas)": 81,
    "Federated States of Micronesia": 82,
    "Faroe Islands": 83,
    "French Polynesia": 84,
    "Baker Island": 85,
    "France": 86,
    "French Southern and Antarctic Lands": 87,
    "Gambia": 88,
    "Gabon": 89,
    "Georgia": 90,
    "Ghana": 91,
    "Gibraltar": 92,
    "Grenada": 93,
    "Guernsey": 94,
    "Greenland": 95,
    "Germany": 96,
    "Glorioso Islands": 97,
    "Guadeloupe": 98,
    "Guam": 99,
    "Greece": 100,
    "Guatemala": 101,
    "Guinea": 102,
    "Guyana": 103,
    "Gaza Strip": 104,
    "Haiti": 105,
    "Hong Kong": 106,
    "Heard Island and McDonald Islands": 107,
    "Honduras": 108,
    "Howland Island": 109,
    "Croatia": 110,
    "Hungary": 111,
    "Iceland": 112,
    "Indonesia": 113,
    "Man, Isle of": 114,
    "India": 115,
    "British Indian Ocean Territory": 116,
    "Clipperton Island": 117,
    "Iran": 118,
    "Israel": 119,
    "Italy": 120,
    "Cote d'Ivoire": 121,
    "Iraq": 122,
    "Japan": 123,
    "Jersey": 124,
    "Jamaica": 125,
    "Jan Mayen": 126,
    "Jordan": 127,
    "Johnston Atoll": 128,
    "Juan de Nova Island": 129,
    "Kenya": 130,
    "Kyrgyzstan": 131,
    "North Korea": 132,
    "Kingman Reef": 133,
    "Kiribati": 134,
    "South Korea": 135,
    "Christmas Island": 136,
    "Kuwait": 137,
    "Kazakhstan": 138,
    "Laos": 139,
    "Lebanon": 140,
    "Latvia": 141,
    "Lithuania": 142,
    "Liberia": 143,
    "Slovakia": 144,
    "Palmyra Atoll": 145,
    "Liechtenstein": 146,
    "Lesotho": 147,
    "Luxembourg": 148,
    "Libya": 149,
    "Madagascar": 150,
    "Martinique": 151,
    "Macau": 152,
    "Moldova": 153,
    "Mayotte": 154,
    "Mongolia": 155,
    "Montserrat": 156,
    "Malawi": 157,
    "Montenegro": 158,
    "Republic of Macedonia": 159,
    "Mali": 160,
    "Monaco": 161,
    "Morocco": 162,
    "Mauritius": 163,
    "Midway Islands": 164,
    "Mauritania": 165,
    "Malta": 166,
    "Oman": 167,
    "Maldives": 168,
    "Mexico": 169,
    "Malaysia": 170,
    "Mozambique": 171,
    "New Caledonia": 172,
    "Niue": 173,
    "Norfolk Island": 174,
    "Niger": 175,
    "Vanuatu": 176,
    "Nigeria": 177,
    "Netherlands": 178,
    "No Man's Land": 179,
    "Norway": 180,
    "Nepal": 181,
    "Nauru": 182,
    "Suriname": 183,
    "Netherlands Antilles": 184,
    "Nicaragua": 185,
    "New Zealand": 186,
    "Paraguay": 187,
    "Pitcairn Islands": 188,
    "Peru": 189,
    "Paracel Islands": 190,
    "Spratly Islands": 191,
    "Pakistan": 192,
    "Poland": 193,
    "Panama": 194,
    "Portugal": 195,
    "Papua New Guinea": 196,
    "Palau": 197,
    "Guinea-Bissau": 198,
    "Qatar": 199,
    "Serbia": 200,
    "Reunion": 201,
    "Marshall Islands": 202,
    "Romania": 203,
    "Philippines": 204,
    "Russia": 205,
    "Rwanda": 206,
    "Saudi Arabia": 207,
    "Saint Pierre and Miquelon": 208,
    "Saint Kitts and Nevis": 209,
    "Seychelles": 210,
    "South Africa": 211,
    "Senegal": 212,
    "Saint Helena": 213,
    "Slovenia": 214,
    "Sierra Leone": 215,
    "San Marino": 216,
    "Singapore": 217,
    "Somalia": 218,
    "Spain": 219,
    "Saint Lucia": 220,
    "Sudan": 221,
    "Svalbard": 222,
    "Sweden": 223,
    "South Georgia and the Islands": 224,
    "Syria": 225,
    "Switzerland": 226,
    "Trinidad and Tobago": 227,
    "Tromelin Island": 228,
    "Thailand": 229,
    "Tajikistan": 230,
    "Turks and Caicos Islands": 231,
    "Tokelau": 232,
    "Tonga": 233,
    "Togo": 234,
    "Sao Tome and Principe": 235,
    "Tunisia": 236,
    "East Timor": 237,
    "Turkey": 238,
    "Tuvalu": 239,
    "Taiwan": 240,
    "Turkmenistan": 241,
    "Tanzania": 242,
    "Uganda": 243,
    "Ukraine": 244,
    "Burkina Faso": 245,
    "Uruguay": 246,
    "Uzbekistan": 247,
    "Saint Vincent and the Grenadines": 248,
    "Venezuela": 249,
}

title_cache = "~salary~glassdoor0302~@"
table = "cache_salary_glassdoor"


async def get_glassdoor_salary(
    job_title, background_task, country, company, es, CACHE=True
):
    if not country:
        country = "United States"
    if not job_title:
        return None
    if "intern" in job_title.lower() and "pakistan" in country.lower():
        return None
    if CACHE == True:
        try:
            cached_data = await get_cached_data(
                job_title + "~" + country + "~" + title_cache, table
            )
            if cached_data:
                return cached_data
        except Exception as e:
            pass
    """
    Retrieves the salary information from Glassdoor for a given job title and returns the salary and the URL where the data was found.

    Args:
        job_title (str): The job title for which to retrieve salary information.

    Returns:
        tuple (float or None, str): The estimated salary for the given job title, and the Glassdoor URL where the data can be viewed.
    """

    final = {
        "title": "",
        "min": None,
        "max": None,
        "average": None,
        "Calculated Considering Company": None,
        "source": "",
    }

    gd_csrf_token = "".join(
        random.choice("0123456789abcdefABCDEFGH") for _ in range(178)
    )
    gd_id = "".join(random.choice("0123456789abcdef") for _ in range(32))
    gd_id = (
        gd_id[:8]
        + "-"
        + gd_id[8:12]
        + "-"
        + gd_id[12:16]
        + "-"
        + gd_id[16:20]
        + "-"
        + gd_id[20:]
    )
    user_id = random.randint(1000000000000000000, 9999999999999999999)

    headers = {
        "authority": "www.glassdoor.com",
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "apollographql-client-name": "salary-search",
        "apollographql-client-version": "10.16.2",
        "cache-control": "no-cache",
        "content-type": "application/json",
        "gd-csrf-token": gd_csrf_token,
        "origin": "https://www.glassdoor.com",
        "pragma": "no-cache",
        "referer": "https://www.glassdoor.com/",
        "sec-ch-ua": '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Linux"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    }

    try:
        idd = Countries_Ids[country]
    except:
        idd = 1
        country = "United States"

    salary_url = f"""https://www.glassdoor.com/Salaries/{country.replace(" ", "-")}-{job_title.replace(' ', '-')}-salary-SRCH_IL.0,{len(country)}_IN{idd}_KO{len(country)+1},{len(country)+len(job_title)+1}.htm"""

    json_data = [
        {
            "operationName": "SalarySearchFAQsQuery",
            "variables": {
                "domain": "glassdoor.com",
                "locale": "en-US",
                "gdId": gd_id,
                "ip": "172.71.190.186,10.0.201.244, 10.0.212.112",
                "userId": user_id,
                "jobTitle": job_title,
                "cityId": None,
                "metroId": None,
                "stateId": None,
                "countryId": idd,
                "industryId": 0,
                "urlData": {
                    "url": "",
                    "searchParams": [{"type": "KO", "value": ""}],
                    "pagePrefix": "IP",
                    "payPeriodFilter": None,
                    "decodedJobTitle": "",
                },
                "useUgcSearch2ForSalaries": "true",
                "enableV3Estimates": "true",
            },
            "query": """query SalarySearchFAQsQuery($cityId: Int, $countryId: Int, $metroId: Int, $stateId: Int, $jobTitle: String!) {
    occSalaryEstimates(
        occSalaryEstimatesInput: {
            jobTitle: {text: $jobTitle}, 
            location: {cityId: $cityId, metroId: $metroId, stateId: $stateId, countryId: $countryId}
        }
    ) {
        additionalPayPercentiles {
            value
            percentile
        }
        basePayPercentiles {
            value
            percentile
        }
        currency {
            code
        }
        jobTitle {
            id
            text
            sgocId
        }
        payPeriod
        queryLocation {
            id
            name
            type
        }
        salariesCount
        totalPayPercentiles {
            value
            percentile
        }
    }
}
""",
        }
    ]

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.post(
                "https://www.glassdoor.com/graph",
                headers=headers,
                json=json_data,
                timeout=10,
            )
        except:
            return None

    salary = 0
    if response.status_code == 200:
        data = response.json()
        # print("data: \n", json.dumps(data), "\n\n")
        if not data[0]["data"]["occSalaryEstimates"]["totalPayPercentiles"]:
            return None

        flag = False
        try:
            if "month" in data[0]["data"]["occSalaryEstimates"]["payPeriod"].lower():
                flag = True
        except:
            pass

        AvgMin = None
        AvgMax = None
        AvgMedian = None
        closest_50 = None
        closest_85 = None
        for percentile in data[0]["data"]["occSalaryEstimates"]["totalPayPercentiles"]:
            nu_mber = int(re.search(r"\d+", percentile["percentile"]).group())
            if AvgMin:
                if percentile["value"] < AvgMin:
                    AvgMin = percentile["value"]
            else:
                AvgMin = percentile["value"]

            # if AvgMax:
            #     if percentile["value"] > AvgMax:
            #         AvgMax = percentile["value"]
            # else:
            #     AvgMax = percentile["value"]

            if closest_50:
                if abs(nu_mber - 50) < closest_50:
                    closest_50 = abs(nu_mber - 50)
                    AvgMedian = percentile["value"]
            else:
                closest_50 = abs(nu_mber - 50)
                AvgMedian = percentile["value"]

            if closest_85:
                if abs(nu_mber - 85) < closest_85:
                    closest_85 = abs(nu_mber - 85)
                    AvgMax = percentile["value"]
            else:
                closest_85 = abs(nu_mber - 85)
                AvgMax = percentile["value"]

        if flag:
            AvgMedian = AvgMedian * 12
            AvgMax = AvgMax * 12
            AvgMin = AvgMin * 12

        if AvgMedian == AvgMin or AvgMedian == AvgMax:
            AvgMedian = None

        final["title"] = job_title
        final["min"] = AvgMin
        final["max"] = AvgMax
        final["average"] = AvgMedian
        final["source"] = salary_url

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
                background_task.add_task(
                    cache_data,
                    job_title + "~" + country + "~" + title_cache,
                    final,
                    table,
                )

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
                    background_task.add_task(
                        cache_data,
                        job_title + "~" + country + "~" + title_cache,
                        final,
                        table,
                    )
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
                background_task.add_task(
                    cache_data,
                    job_title + "~" + country + "~" + title_cache,
                    final,
                    table,
                )

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
            background_task.add_task(
                cache_data,
                job_title + "~" + country + "~" + title_cache,
                final,
                table,
            )
        return final

    else:
        print(f"Request failed with status code: {response.status_code}")
        print("Reason:", response.text)
        return (
            None,
            salary_url,
        )
