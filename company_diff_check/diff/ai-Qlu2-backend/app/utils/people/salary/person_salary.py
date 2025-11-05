import re
import os
import string
import asyncio
import tldextract
from dateutil import parser
from datetime import datetime

from qutils.llm.asynchronous import invoke
from qutils.database.post_gres import postgres_fetch_profile_data

from app.utils.people.salary.similar_approach import executive_salaries_company
from app.utils.people.salary.openai_executive import executive_or_not
from app.utils.people.salary.inflation_adjustment import (
    calculate_past_salary,
    get_currency_code,
)
from app.utils.people.salary.salary_com_original import executive_salaries
from app.utils.people.salary.glassdoor_salary import get_glassdoor_salary
from app.utils.people.salary.rapid_api import RapidApi
from app.core.database import get_cached_data, cache_data

from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync
from forex_python.converter import CurrencyCodes

c = CurrencyCodes()


token = os.getenv("TOKEN")
org = os.getenv("SITE")
url = os.getenv("URL")
__client = None

table = "cache_salary_person"
full_cache = "~individual_salary0302-~@"


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


def remove_punctuation(title):
    translator = str.maketrans("", "", string.punctuation)
    return title.translate(translator)


async def country_name(title):
    if not title:
        return None
    messages = [
        {
            "role": "system",
            "content": "You are an intelligent assistant, You have to return the country name according to the details provided to you. If country name can't be figured out, then return None.",
        }
    ]

    user_query = """Return the country name according to the details provided to you. Details can be any city name, country name, area name, etc. If country name can't be figured out, then return None.
    ONLY return the country name. DO NOT INCLUDE ANY OTHER TEXT IN YOUR OUTPUT"""
    messages.append({"role": "user", "content": user_query + "\n" + title})

    completion = await invoke(
        messages=messages,
        model="openai/gpt-4o-mini",
        temperature=0,
        fallbacks=["anthropic/claude-3-5-haiku-latest"],
    )
    return completion


async def normalize_title(title):
    messages = [
        {
            "role": "system",
            "content": """
                You are an intelligent assistant, you have to normalize titles.
                If multiple titles are mentioned use the most relevant title.
                Important note: Always just return the title in our output.

            """,
        }
    ]
    user_query = """
    Return the most relevant title which accurately describes the role of the person. Do not understate the role. For example, a Chief Finance Officer can never be Finance Officer. Ensure the relevance of the person is maintained.
    Also convert to full title wherever possible.
                Examples:
                User: Cofounder & CTO at Databricks, CS Professor at Berkeley
                Output: Chief Technology Officer
                
                """
    messages.append({"role": "user", "content": user_query + title})

    completion = await invoke(
        messages=messages,
        model="openai/gpt-4o-mini",
        temperature=0,
        fallbacks=["anthropic/claude-3-5-haiku-latest"],
    )
    return completion


async def currency_converter(currency_code):
    if not currency_code:
        return "USD"
    messages = [
        {
            "role": "system",
            "content": """
                You are an intelligent assistant whose job is to convert currency codes to English.
                You are only allowed to return the resulting code in our output nothing else!

                Example:
                User: "د.إ;"
                Response: "AED"
            """,
        }
    ]
    messages.append({"role": "user", "content": currency_code})

    completion = await invoke(
        messages=messages,
        temperature=0,
        model="openai/gpt-4o-mini",
        fallbacks=["anthropic/claude-3-5-haiku-latest"],
    )
    return completion


async def salarycomscraper(fullname, title_company_pairs, es):
    tasks = []
    for pair in title_company_pairs:
        tasks.append(executive_salaries(fullname, pair[1], pair[2], es))
    results = await asyncio.gather(*tasks, return_exceptions=True)

    results = [
        result for result in results if (not isinstance(result, IndexError)) and result
    ]

    tuples = []
    for pair in title_company_pairs:
        tuples.append((pair[0], pair[1]))

    for (executive_salary, source), (title, company) in zip(results, tuples):
        if isinstance(executive_salary, Exception):
            continue
        if executive_salary and len(executive_salary) > 0:
            result = {}
            for key, value in executive_salary.items():
                if value:
                    result.update(
                        {
                            key: {
                                "title": [title],
                                "baseSalary": value.get("basePay", "Not provided"),
                                "equity": value.get("totalEquity", "Not provided"),
                                "nonEquity": value.get("bonusIncentiveCompensation", 0)
                                + value.get("totalOther", 0),
                                "total": value.get("totalCompensation", "Not provided"),
                                "source": {
                                    title: source.get("def_14", "source not available")
                                },
                            }
                        }
                    )
            years_to_remove = []
            for year, data in result.items():
                string_values = [
                    str(value).lower() for value in data["source"].values()
                ]
                if (
                    not data["title"]
                    or data["total"] == "Not provided"
                    or "source not available" in string_values
                ):
                    years_to_remove.append(year)

            for year in years_to_remove:
                del result[year]

            if len(result) > 0:
                return result
    return None


async def salaryglassscraper(
    titles, companies, year, background_task, country, currency, es
):

    tasks = []

    titles = list(dict.fromkeys(titles))

    try:

        response = []
        for number in range(len(titles)):
            tasks.append(
                get_glassdoor_salary(
                    titles[number], background_task, country, companies[number], es
                )
            )
        response = await asyncio.gather(*tasks)

        remaining_titles = []
        to_remove = []
        remaining_companies = []
        for i in range(len(response)):
            if not response[i]:
                remaining_titles.append(titles[i])
                to_remove.append(response[i])
                remaining_companies.append(companies[i])

        for j in to_remove:
            response.remove(j)

        tasks = []
        for number in range(len(remaining_titles)):
            tasks.append(
                RapidApi(
                    remaining_companies[number],
                    remaining_titles[number],
                    country,
                    2000,
                    background_task,
                    es,
                )
            )
        try:
            response11 = await asyncio.gather(*tasks)
            response = response + response11
        except Exception as e:
            print(e)
            pass

        salaries = []

        response = [i.copy() for i in response if i]

        for row in response:
            if row["Calculated Considering Company"]:
                salary = row["Calculated Considering Company"]
            elif row["average"]:
                salary = row["average"]
            elif row["max"]:
                salary = row["max"]
            else:
                salary = row["min"]

            if salary:
                if year == 2024:
                    salary_ = round(salary)
                else:
                    try:
                        salary_ = round(calculate_past_salary(year, country, salary))
                    except:
                        salary_ = round(
                            calculate_past_salary(year, "United States", salary)
                        )

                row["Salary adjusting for inflation of country"] = (
                    "USD" + " " + str("{:,}".format(salary_))
                )
                salaries.append(salary_)

            if row["Calculated Considering Company"]:
                row["Calculated Considering Company"] = (
                    currency
                    + " "
                    + str("{:,}".format(round(row["Calculated Considering Company"])))
                )
            if row["average"]:
                row["average"] = (
                    currency + " " + str("{:,}".format(round(row["average"])))
                )
            if row["max"]:
                row["max"] = currency + " " + str("{:,}".format(round(row["max"])))
            if row["min"]:
                row["min"] = currency + " " + str("{:,}".format(round(row["min"])))

        final = {"salary": None, "details": response}

        if len(salaries) > 0:
            sal = sum(salaries) / len(salaries)
            final["salary"] = sal

        return final
    except Exception as e:
        print("issue")
        raise e


def extract_year(date):
    try:
        date_obj = parser.parse(date, fuzzy=True)
        return date_obj.year
    except Exception as exception:
        match = re.search(r"\b(?:19|20)\d{2}\b", date)
        if match:
            return int(match.group())
        else:
            raise exception


def transform_postgres_response(postgres_response):
    transformed_data = {
        "experience": [],
        "publicIdentifier": postgres_response["profile"]["public_identifier"],
        "firstName": postgres_response["profile"]["first_name"],
        "lastName": postgres_response["profile"]["last_name"],
        "fullName": postgres_response["profile"]["full_name"],
        "locationFullPath": (
            postgres_response["location"][0]["location"]
            if postgres_response["location"]
            else ""
        ),
        "locationName": (
            postgres_response["location"][0]["country"]
            if postgres_response["location"]
            else ""
        ),
    }

    for exp in postgres_response["experience"]:
        experience_entry = {
            "title": exp["title"],
            "company_name": "",
            "location": exp["location"] if exp["location"] else "",
            "start": (
                parser.parse(exp["start"]).strftime("%Y")
                if exp["start"]
                and parser.parse(exp["start"]).day == 1
                and parser.parse(exp["start"]).month == 1
                else (
                    parser.parse(exp["start"]).strftime("%b %Y") if exp["start"] else ""
                )
            ),
            "end": (
                "Present"
                if exp["end"] is None
                else (
                    parser.parse(exp["end"]).strftime("%Y")
                    if exp["end"]
                    and parser.parse(exp["end"]).day == 1
                    and parser.parse(exp["end"]).month == 1
                    else (
                        parser.parse(exp["end"]).strftime("%b %Y") if exp["end"] else ""
                    )
                )
            ),
            "urn": "",
            "universalName": "",
        }

        transformed_data["experience"].append(experience_entry)

    for exp in transformed_data["experience"]:
        exp_index = transformed_data["experience"].index(exp)
        company_data = (
            postgres_response["companies"][exp_index]
            if exp_index < len(postgres_response["companies"])
            else {}
        )

        if company_data:
            exp["company_name"] = company_data["name"] if "name" in company_data else ""
            exp["urn"] = (
                f"urn:li:fsd_company:{company_data['urn']}"
                if "urn" in company_data
                else ""
            )
            exp["universalName"] = (
                company_data["universal_name"]
                if "universal_name" in company_data
                else ""
            )

    for key, value in transformed_data.items():
        if isinstance(value, str) and value is None:
            transformed_data[key] = ""
        elif isinstance(value, list):
            for entry in value:
                for sub_key in entry.keys():
                    if entry[sub_key] is None:
                        entry[sub_key] = ""

    return transformed_data


async def main(id, background_task, es, db, CACHE=True):
    if CACHE == True:
        try:
            cached_data = await get_cached_data(id + full_cache, table)
            if cached_data:
                return cached_data
        except Exception as e:
            pass

    try:
        result = await postgres_fetch_profile_data(
            db, [id], ["experience", "location", "companies"]
        )

        if result is None:
            return {"message": "User Not Found"}
        else:
            result = transform_postgres_response(result[id])

    except Exception as e:
        print(f"An error occurred while fetching data from postgreSQL: {e}")
        return {"message": "User Not Found"}

    PUBLIC_IDENTIFIER_BROTHERS = result["publicIdentifier"]
    if result is None:
        return {"message": "User Not Found"}

    country = (
        result["locationName"] + " - " + result["locationFullPath"]
        if (result["locationName"] and result["locationFullPath"])
        else None
    )
    if not country:
        try:
            country = str(result["experience"][0]["location"])
        except:
            pass
    try:
        country = await country_name(country)
        cur = get_currency_code(country)
        cur = c.get_symbol(cur)
        if cur.isascii() == False:
            cur = await currency_converter(cur)
    except:
        cur = None

    if not cur:
        cur = "USD"
    currency = cur
    titleS = []
    COMPANIES = []
    if "experience" in result:
        result["experience"] = [exp for exp in result["experience"] if exp["title"]]
        for experience in result["experience"]:
            titleS.append(experience["title"])
            if experience["universalName"]:
                COMPANIES.append(experience["universalName"])
            else:
                if "urn" in experience.keys():
                    if experience["urn"]:
                        query = {
                            "size": 1,
                            "_source": [
                                "li_universalname",
                            ],
                            "query": {"term": {"li_urn": {"value": experience["urn"]}}},
                        }

                        res = await es.search(
                            index=os.getenv("ES_COMPANIES_INDEX"), body=query
                        )
                        try:
                            COMPANIES.append(
                                res["hits"]["hits"][0]["_source"]["li_universalname"]
                            )
                        except:
                            COMPANIES.append("")

    tasks = []
    for title in titleS:
        tasks.append(normalize_title(title))
    titleS = await asyncio.gather(*tasks)

    for index, title in enumerate(titleS):
        titleS[index] = remove_punctuation(title)

    for i in range(len(result["experience"])):
        result["experience"][i]["title"] = titleS[i]

    result = {k: v for k, v in result.items() if v is not None and v != [] and v != ""}
    if "experience" not in result or result == {}:
        return {"message": "Low information profile"}

    if "fullName" not in result or result["fullName"] == "":
        if "firstName" in result:
            result["fullName"] = result["firstName"]
            if "lastName" in result:
                result["fullName"] += " " + result["lastName"]

    recent_experience = result["experience"][0]

    query1 = {
        "size": 1,
        "_source": ["li_universalname", "yf_market.longname"],
        "query": {
            "term": {"li_universalname": {"value": recent_experience["universalName"]}}
        },
    }

    try:
        res_comp = await es.search(index=os.getenv("ES_COMPANIES_INDEX"), body=query1)
        recent_experience["company_name"] = res_comp["hits"]["hits"][0]["_source"][
            "yf_market"
        ][0]["longname"]
    except:
        pass
    recent_experience["title"] = titleS[0]

    title_company_pairs = []
    for exp in result["experience"]:
        ti = exp["title"]
        comp = exp["company_name"]
        uni = exp["universalName"]

        if not uni:
            if "urn" in exp.keys():
                if exp["urn"]:
                    query = {
                        "size": 1,
                        "_source": [
                            "li_universalname",
                        ],
                        "query": {"term": {"li_urn": {"value": exp["urn"]}}},
                    }

                    res = await es.search(
                        index=os.getenv("ES_COMPANIES_INDEX"), body=query
                    )
                    try:
                        uni = res["hits"]["hits"][0]["_source"]["li_universalname"]
                    except:
                        uni = ""

        title_company_pairs.append([ti, comp, uni])

    if recent_experience["universalName"]:
        executive_salary = await salarycomscraper(
            result["fullName"], title_company_pairs, es
        )
        if executive_salary:
            for i in executive_salary:
                executive_salary[i]["baseSalary"] = (
                    cur + " " + str("{:,}".format(executive_salary[i]["baseSalary"]))
                )
                executive_salary[i]["equity"] = (
                    cur + " " + str("{:,}".format(executive_salary[i]["equity"]))
                )
                executive_salary[i]["total"] = (
                    cur + " " + str("{:,}".format(executive_salary[i]["total"]))
                )
                executive_salary[i]["nonEquity"] = (
                    cur + " " + str("{:,}".format(executive_salary[i]["nonEquity"]))
                )
                for j in executive_salary[i]["source"]:
                    executive_salary[i]["source"][j] = {
                        "SEC": "https://" + executive_salary[i]["source"][j]
                    }
            if CACHE == True:
                background_task.add_task(
                    cache_data, id + full_cache, executive_salary, table
                )
            return executive_salary
        else:
            for item in result["experience"]:
                if (
                    item["end"] == ""
                    or item["end"].lower() == "present"
                    or item["end"].lower() == "undefined"
                ):
                    item["end"] = str(datetime.now().year)

                if item["start"] == "":
                    item["start"] = str(datetime.now().year)

                item["end"] = extract_year(item["end"])
                item["start"] = extract_year(item["start"])

                if item["start"] > item["end"]:
                    item["start"] = item["end"]

            title_years = {
                i: [] for i in range(datetime.now().year - 4, datetime.now().year + 1)
            }

            company_years = {
                i: [] for i in range(datetime.now().year - 4, datetime.now().year + 1)
            }
            for item in result["experience"]:
                try:
                    if not item["start"]:
                        continue
                    if int(item["start"]) in title_years:

                        if not item["universalName"]:
                            if "urn" in item.keys():
                                if item["urn"]:
                                    query = {
                                        "size": 1,
                                        "_source": [
                                            "li_universalname",
                                        ],
                                        "query": {
                                            "term": {"li_urn": {"value": item["urn"]}}
                                        },
                                    }

                                    res = await es.search(
                                        index=os.getenv("ES_COMPANIES_INDEX"),
                                        body=query,
                                    )
                                    try:
                                        item["universalName"] = res["hits"]["hits"][0][
                                            "_source"
                                        ]["li_universalname"]
                                    except:
                                        item["universalName"] = ""

                        if not item["universalName"]:
                            continue

                        if len(title_years[int(item["start"])]) == 0:
                            title_years[int(item["start"])] = [item["title"]]
                            company_years[int(item["start"])] = [item["universalName"]]
                        else:
                            title_years[int(item["start"])].append(item["title"])
                            company_years[int(item["start"])].append(
                                item["universalName"]
                            )
                except Exception as e:
                    print(f"Exception: {e}")

            for key, value in title_years.items():
                for item in result["experience"]:
                    if not item["start"]:
                        continue
                    if key > int(item["start"]) and key <= int(item["end"]):

                        if not item["universalName"] and "urn" in item.keys():
                            if item["urn"]:
                                query = {
                                    "size": 1,
                                    "_source": [
                                        "li_universalname",
                                    ],
                                    "query": {
                                        "term": {"li_urn": {"value": item["urn"]}}
                                    },
                                }

                                res = await es.search(
                                    index=os.getenv("ES_COMPANIES_INDEX"), body=query
                                )
                                try:
                                    item["universalName"] = res["hits"]["hits"][0][
                                        "_source"
                                    ]["li_universalname"]
                                except:
                                    item["universalName"] = ""

                        if not item["universalName"]:
                            continue
                        company_years[key].append(item["universalName"])
                        title_years[key].append(item["title"])

            non_empty_values = [v for v in company_years.values() if v]
            salary_data = {}
            for i in range(datetime.now().year, datetime.now().year - 5, -1):
                year = i
                titles = title_years[year]
                companies = company_years[year]
                for l in range(len(titles) - 1, -1, -1):
                    if "student" in titles[l].lower():
                        titles.pop(l)
                        companies.pop(l)
                if titles != []:
                    result = await salaryglassscraper(
                        titles, companies, year, background_task, country, cur, es
                    )

                    if result["salary"]:
                        for row in result["details"]:
                            extracted_info = tldextract.extract(row["source"])
                            if extracted_info.domain:
                                row["source"] = {
                                    extracted_info.domain.title(): row["source"]
                                }
                            else:
                                name = row["source"].split(".")
                                name = name[1].split(".")
                                row["source"] = {name[0].title(): row["source"]}

                        salary_data[year] = {
                            "title": titles,
                            "salary": round(result["salary"]),
                            "details": result["details"],
                        }
                    else:
                        salary_data[year] = {
                            "title": titles,
                            "salary": None,
                            "details": None,
                        }

            salary_data = {
                year: data
                for year, data in salary_data.items()
                if data["salary"] is not None
            }

            exec_years = []
            exec_tasks = []
            for key, value in title_years.items():
                task = asyncio.create_task(executive_or_not(str(value)))
                exec_tasks.append((key, value, task))

            results = await asyncio.gather(*[task for _, _, task in exec_tasks])
            for (key, value, task), answer in zip(exec_tasks, results):
                if "yes" in answer.lower():
                    exec_years.append(key)

            if not exec_years:
                temp_salary_data = {}
                for year in salary_data.keys():
                    temp_salary_data[year] = {
                        "title": salary_data[year]["title"],
                        "baseSalary": currency
                        + " "
                        + str("{:,}".format(round(salary_data[year]["salary"]))),
                        "total": currency
                        + " "
                        + str("{:,}".format(round(salary_data[year]["salary"]))),
                        "source": {
                            salary_data[year]["details"][ttt]["title"]: salary_data[
                                year
                            ]["details"][ttt]["source"]
                            for ttt in range(len(salary_data[year]["details"]))
                        },
                        "equity": None,
                        "nonEquity": None,
                    }

                if CACHE == True:
                    background_task.add_task(
                        cache_data, id + full_cache, temp_salary_data, table
                    )
                return temp_salary_data

            count_salary_com = True
            tasks_salary_com = []
            names_done = []

            names_of_companies = []
            for index, company in company_years.items():
                if index not in exec_years:
                    continue
                if company[0] in names_done:
                    continue
                if count_salary_com:
                    names_of_companies.append(recent_experience["universalName"])
                    tasks_salary_com.append(
                        executive_salaries_company(
                            recent_experience["company_name"],
                            recent_experience["universalName"],
                            es,
                        )
                    )
                    names_done.append(recent_experience["universalName"])
                    count_salary_com = False
                else:
                    names_of_companies.append(company[0])
                    tasks_salary_com.append(
                        executive_salaries_company("", company[0], es)
                    )
                    names_done.append(company[0])

            all_results = await asyncio.gather(*tasks_salary_com)
            if not any(all_results):
                temp_salary_data = {}
                for year in salary_data.keys():
                    base = (
                        currency
                        + " "
                        + str("{:,}".format(round(salary_data[year]["salary"])))
                    )

                    temp_salary_data[year] = {
                        "title": salary_data[year]["title"],
                        "baseSalary": base,
                        "total": base,
                        "source": {
                            salary_data[year]["details"][ttt]["title"]: salary_data[
                                year
                            ]["details"][ttt]["source"]
                            for ttt in range(len(salary_data[year]["details"]))
                        },
                        "equity": None,
                        "nonEquity": None,
                    }

                if CACHE == True:
                    background_task.add_task(
                        cache_data, id + full_cache, temp_salary_data, table
                    )
                return temp_salary_data

            for index, result in enumerate(all_results):
                if result:
                    result = {
                        int(year): data
                        for year, data in result.items()
                        if (
                            int(year) in company_years
                            and names_of_companies[index] in company_years[int(year)]
                            and data
                        )
                    }

                    for year, positions in result.items():
                        lowest_total = float("inf")
                        lowest_position = None

                        count_base = 0
                        base_sal = 0
                        for position, details in positions.items():
                            if (
                                details["total"] < lowest_total
                                and details["baseSalary"] > 0
                            ):
                                lowest_total = details["total"]
                                lowest_position = position

                                count_base = count_base + 1
                                base_sal = base_sal + details["baseSalary"]

                        if lowest_total == float("inf"):
                            for position, details in positions.items():
                                if details["total"] < lowest_total:
                                    lowest_total = details["total"]
                                    lowest_position = position

                        if count_base:
                            calculated_base = base_sal // count_base
                        else:
                            calculated_base = 0

                        result[year]["Lowest"] = {
                            "title": lowest_position,
                            "baseSalary": calculated_base,
                            "equity": positions[lowest_position]["equity"],
                            "nonEquity": positions[lowest_position]["nonEquity"],
                            "total": calculated_base
                            + positions[lowest_position]["equity"]
                            + positions[lowest_position]["nonEquity"],
                        }

                    all_results[index] = result

            all_results = [result for result in all_results if result]

            to_keep = []

            tempyear1 = None

            salary_data = {
                key: salary_data[key]
                for key in sorted(salary_data.keys(), reverse=True)
            }

            calculated_ratio = {}
            for i in salary_data:
                ratio = 0
                tempyear = None
                for result in all_results:
                    if i in result:
                        tempsalary = None

                        if tempyear:
                            tempratio = (
                                result[i]["Lowest"]["total"]
                                / result[tempyear]["Lowest"]["total"]
                            )
                            if tempratio < 1:
                                tempsalary = salary_data[i]["salary"] * tempratio

                        if not tempsalary:
                            tempsalary = salary_data[i]["salary"]

                        try:
                            ratio = tempsalary / result[i]["Lowest"]["baseSalary"]
                        except:
                            ratio = 1
                            pass
                        calculated_ratio[i] = ratio

                        salary_data[i]["equity"] = result[i]["Lowest"]["equity"] * ratio

                        salary_data[i]["nonEquity"] = (
                            result[i]["Lowest"]["nonEquity"] * ratio
                        )
                        salary_data[i]["total"] = (
                            salary_data[i]["nonEquity"]
                            + salary_data[i]["equity"]
                            + salary_data[i]["salary"]
                        )
                        salary_data[i]["baseSalary"] = salary_data[i]["salary"]
                        salary_data[i]["source"] = {
                            salary_data[i]["details"][ttt]["title"]: salary_data[i][
                                "details"
                            ][ttt]["source"]
                            for ttt in range(len(salary_data[i]["details"]))
                        }
                        salary_data[i].pop("salary", None)
                        salary_data[i].pop("details", None)

                        if salary_data[i]["total"] > result[i]["Lowest"]["total"]:

                            main_title_temp = await normalize_title(
                                result[i]["Lowest"]["title"]
                            )
                            main_title_temp = remove_punctuation(main_title_temp)

                            tasks = []
                            tasks.append(
                                salaryglassscraper(
                                    [main_title_temp],
                                    [recent_experience["universalName"]],
                                    i,
                                    background_task,
                                    country,
                                    currency,
                                    es,
                                )
                            )

                            tasks.append(
                                salaryglassscraper(
                                    [salary_data[i]["title"][0]],
                                    [recent_experience["universalName"]],
                                    i,
                                    background_task,
                                    country,
                                    currency,
                                    es,
                                )
                            )

                            executive_1_temp, executive_2_temp = await asyncio.gather(
                                *tasks
                            )
                            title_diff_ratio = 1
                            try:
                                executive_1 = executive_1_temp["details"][0]
                                executive_2 = executive_2_temp["details"][0]

                                value_1 = int(
                                    executive_1["max"]
                                    .replace(currency + " ", "")
                                    .replace(",", "")
                                )
                                value_2 = int(
                                    executive_2["max"]
                                    .replace(currency + " ", "")
                                    .replace(",", "")
                                )
                                value_3 = int(
                                    executive_2["average"]
                                    .replace(currency + " ", "")
                                    .replace(",", "")
                                )
                                if value_1 > value_2:
                                    title_diff_ratio = value_2 / value_1
                                elif value_1 > value_3:
                                    title_diff_ratio = value_3 / value_1

                            except:
                                pass

                            salary_data[i]["nonEquity"] = (
                                result[i]["Lowest"]["nonEquity"] * title_diff_ratio
                            )
                            salary_data[i]["equity"] = (
                                result[i]["Lowest"]["equity"] * title_diff_ratio
                            )
                            salary_data[i]["baseSalary"] = (
                                result[i]["Lowest"]["baseSalary"] * title_diff_ratio
                            )

                            salary_data[i]["total"] = (
                                salary_data[i]["nonEquity"]
                                + salary_data[i]["equity"]
                                + salary_data[i]["baseSalary"]
                            )

                            salary_data[i]["total"] = (
                                currency
                                + " "
                                + str("{:,}".format(round(salary_data[i]["total"])))
                            )
                        else:
                            salary_data[i]["total"] = (
                                currency
                                + " "
                                + str("{:,}".format(round(salary_data[i]["total"])))
                            )

                        salary_data[i]["nonEquity"] = (
                            currency
                            + " "
                            + str("{:,}".format(round(salary_data[i]["nonEquity"])))
                        )
                        salary_data[i]["equity"] = (
                            currency
                            + " "
                            + str("{:,}".format(round(salary_data[i]["equity"])))
                        )
                        salary_data[i]["baseSalary"] = (
                            currency
                            + " "
                            + str("{:,}".format(round(salary_data[i]["baseSalary"])))
                        )

                        tempyear = i
                        break

                if not tempyear:
                    base = (
                        currency
                        + " "
                        + str("{:,}".format(round(salary_data[i]["salary"])))
                    )
                    salary_data[i] = {
                        "title": salary_data[i]["title"],
                        "baseSalary": base,
                        "total": base,
                        "source": {
                            salary_data[i]["details"][ttt]["title"]: salary_data[i][
                                "details"
                            ][ttt]["source"]
                            for ttt in range(len(salary_data[i]["details"]))
                        },
                        "equity": None,
                        "nonEquity": None,
                    }

            if CACHE == True:
                background_task.add_task(
                    cache_data, id + full_cache, salary_data, table
                )
            return salary_data

    else:
        for item in result["experience"]:
            if item["end"] == "" or item["end"].lower() == "present":
                item["end"] = str(datetime.now().year)

            if item["start"] == "":
                item["start"] = str(datetime.now().year)

            item["end"] = extract_year(item["end"])
            item["start"] = extract_year(item["start"])

            if item["start"] > item["end"]:
                item["start"] = item["end"]

        title_years = {
            i: [] for i in range(datetime.now().year - 4, datetime.now().year + 1)
        }

        company_years = {
            i: [] for i in range(datetime.now().year - 4, datetime.now().year + 1)
        }
        for item in result["experience"]:
            try:
                if not item["start"]:
                    continue
                if int(item["start"]) in title_years:

                    if not item["universalName"]:
                        if "urn" in item.keys():
                            if item["urn"]:
                                query = {
                                    "size": 1,
                                    "_source": [
                                        "li_universalname",
                                    ],
                                    "query": {
                                        "term": {"li_urn": {"value": item["urn"]}}
                                    },
                                }

                                res = await es.search(
                                    index=os.getenv("ES_COMPANIES_INDEX"), body=query
                                )
                                try:
                                    item["universalName"] = res["hits"]["hits"][0][
                                        "_source"
                                    ]["li_universalname"]
                                except:
                                    item["universalName"] = ""

                    if not item["universalName"]:
                        continue

                    if len(title_years[int(item["start"])]) == 0:
                        title_years[int(item["start"])] = [item["title"]]
                        company_years[int(item["start"])] = [item["universalName"]]
                    else:
                        title_years[int(item["start"])].append(item["title"])
                        company_years[int(item["start"])].append(item["universalName"])
            except Exception as e:
                print(f"Exception: {e}")

        for key, value in title_years.items():
            for item in result["experience"]:
                if not item["start"]:
                    continue
                if key > int(item["start"]) and key <= int(item["end"]):

                    if not item["universalName"] and "urn" in item.keys():
                        if item["urn"]:
                            query = {
                                "size": 1,
                                "_source": [
                                    "li_universalname",
                                ],
                                "query": {"term": {"li_urn": {"value": item["urn"]}}},
                            }

                            res = await es.search(
                                index=os.getenv("ES_COMPANIES_INDEX"), body=query
                            )
                            try:
                                item["universalName"] = res["hits"]["hits"][0][
                                    "_source"
                                ]["li_universalname"]
                            except:
                                item["universalName"] = ""

                    company_years[key].append(item["universalName"])
                    title_years[key].append(item["title"])

        non_empty_values = [v for v in company_years.values() if v]

        salary_data = {}
        for i in range(datetime.now().year, datetime.now().year - 5, -1):
            year = i
            titles = title_years[year]
            companies = company_years[year]
            for l in range(len(titles) - 1, -1, -1):
                if "student" in titles[l].lower():
                    titles.pop(l)
                    companies.pop(l)
            if titles != []:
                result = await salaryglassscraper(
                    titles, companies, year, background_task, country, cur, es
                )

                if result["salary"]:
                    for row in result["details"]:
                        extracted_info = tldextract.extract(row["source"])
                        if extracted_info.domain:
                            row["source"] = {
                                extracted_info.domain.title(): row["source"]
                            }
                        else:
                            name = row["source"].split(".")
                            name = name[1].split(".")
                            row["source"] = {name[0].title(): row["source"]}

                    salary_data[year] = {
                        "title": titles,
                        "salary": round(result["salary"]),
                        "details": result["details"],
                    }
                else:
                    salary_data[year] = {
                        "title": titles,
                        "salary": None,
                        "details": None,
                    }
                    CACHE = False

        salary_data = {
            year: data
            for year, data in salary_data.items()
            if data["salary"] is not None
        }

        temp_salary_data = {}
        for year in salary_data.keys():
            temp_salary_data[year] = {
                "title": salary_data[year]["title"],
                "baseSalary": currency
                + " "
                + str("{:,}".format(round(salary_data[year]["salary"]))),
                "total": currency
                + " "
                + str("{:,}".format(round(salary_data[year]["salary"]))),
                "source": {
                    salary_data[year]["details"][ttt]["title"]: salary_data[year][
                        "details"
                    ][ttt]["source"]
                    for ttt in range(len(salary_data[year]["details"]))
                },
                "equity": None,
                "nonEquity": None,
            }

        if CACHE == True:
            background_task.add_task(
                cache_data, id + full_cache, temp_salary_data, table
            )
        return temp_salary_data
