import re
import os
import httpx
import string
import random
import asyncio
from bs4 import BeautifulSoup

from qutils.llm.asynchronous import invoke

from datetime import datetime
from urllib.parse import quote_plus, unquote_plus
from app.core.database import cache_data, get_cached_data
from qutils.websearch.websearch import search_google


title_in_table = "~company_exec_details_from_sec@"
table = "cache_salary_sec"


def parse_url(url):
    param_start = url.find("&sa=")
    if param_start != -1:
        url = url[:param_start]
    return url


async def get_cik_id_web(STOCK_NAME, COMPANY_NAME):
    html = await search_google(
        "https://www.google.com/search",
        params={
            "q": f"""site:sec.gov/archives/edgar/data ("{STOCK_NAME}" AND "{COMPANY_NAME}")""",
            "num": 10,
        },
        request_number=3,
    )
    if html != None:
        soup = BeautifulSoup(html, "html.parser")
        divs = soup.find_all("div", attrs={"class": "Gx5Zad fP1Qef xpd EtOod pkphOe"})
        for div in divs:
            link_element = div.find("a", href=True)
            if link_element:
                link = link_element["href"]
                link = unquote_plus(link)
        URL = parse_url(link.split("/url?q=")[1])
        if (".htm" or ".html") in URL:
            return URL.split("/")[6]
        else:
            return None
    return "Websearch failed!"


# async def sec_url_scraping(universalName, CACHE=True):
#     if CACHE == True:
#         try:
#             check_cache = await get_cached_data(
#                 universalName + "~formlinks@", "cache_salary_sec"
#             )
#             if check_cache:
#                 return check_cache
#         except:
#             pass
#     connection = make_es_connection(True)
#     response = await connection.search(
#         index=os.getenv('ES_COMPANIES_INDEX'),
#         body={"query": {"term": {"li_universalname": {"value": universalName}}}},
#     )
#     await connection.close()
#     response = (
#         response["hits"]["hits"][0]["_source"]
#         if response["hits"]["total"]["value"] > 0
#         else None
#     )

#     if not response:
#         return {"message": "company not found"}

#     tasks = []

#     stock_symbol = (
#         response["cb_stock_symbol"]
#         if "cb_stock_symbol" in response and response["cb_stock_symbol"]
#         else ""
#     )
#     if stock_symbol:
#         tasks.append(fetch_cik_id_from_index(stock_symbol))

#     company_name = response["li_name"]

#     if (
#         "yf_market" in response
#         and response["yf_market"]
#         and "longname" in response["yf_market"]
#         and response["yf_market"]["longname"]
#     ):
#         company_name = response["yf_market"]["longname"]

#     tasks.append(fetch_cik_id_from_index(company_name))

#     cik_id = None
#     results = await asyncio.gather(*tasks)
#     for result in results:
#         if result:
#             cik_id, entity = result
#             break

#     url = await fetch_data(cik_id, entity)
#     first = url.split(":")[0].replace("-", "")
#     second = url.split(":")[1]
#     source_url = f"https://www.sec.gov/Archives/edgar/data/{cik_id}/{first}/{second}"
#     return {"def14": source_url}


async def fetch_cik_id_from_index(search_term):

    req_url = f"https://efts.sec.gov/LATEST/search-index?keysTyped={search_term}"

    headers_list = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "accept-language": "en-US,en;q=0.9",
        "origin": "https://www.sec.gov",
        "priority": "u=1, i",
        "referer": "https://www.sec.gov/",
        "sec-ch-ua": 'Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": "Android",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(req_url, headers=headers_list)
        new_response = response.json()

    cikk = (
        new_response["hits"]["hits"][0]["_id"]
        if new_response["hits"]["hits"][0]["_id"]
        else None
    )
    entity = (
        new_response["hits"]["hits"][0]["_source"]["entity"]
        if new_response["hits"]["hits"][0]["_source"]["entity"]
        else None
    )
    return cikk, entity


async def fetch_data(cikk, entity):
    cik = str("0" * (10 - len(cikk))) + cikk
    req_url = f"""https://efts.sec.gov/LATEST/search-index?category=custom&ciks={cik}&entityName={entity.replace(" ", "%20")}%20(CIK%20{cik})&forms=DEF%2014A&startdt=2023-01-01&enddt=2024-12-12"""

    headers_list = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "accept-language": "en-US,en;q=0.9",
        "origin": "https://www.sec.gov",
        "priority": "u=1, i",
        "referer": "https://www.sec.gov/",
        "sec-ch-ua": 'Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": "Android",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(req_url, headers=headers_list)

    return response.json()["hits"]["hits"][0]["_id"]


async def fetch_company_data_from_SEC_ES(cik_id):
    await asyncio.sleep(random.uniform(1.0, 1.5))
    cik_id = str("0" * (10 - len(cik_id))) + cik_id
    url = f"https://data.sec.gov/submissions/CIK{cik_id}.json"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/116.0",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Origin": "https://www.sec.gov",
        "Connection": "keep-alive",
        "Referer": "https://www.sec.gov/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "TE": "trailers",
        "Cookie": "ak_bmsc=827F586BC5C6DB21DE735C89AE30C535~000000000000000000000000000000~YAAQrf4SAk/9IE2KAQAAhWr9bhVqmLNyYTvlLxdAM5emSMsberHyaL944A+rEx2W5mPsiKpAFh0UsJX6UdOvfBdtm7gmUgfVpCPbzvA1qyyBrOdjorhmX+nBV7Y8qy7zgdAKNKIu+Je0Uv5tu0H3OvdEt6nJe5XkXQnaFhOZyHdde2rFPPsvEZ77LR+Ney3AOuzBVQ3E9S7L0QzgOeV8lkxmUeyv8nFKk2u78nws6T56WBrHaKa3jYDc03+rKmNNTSmswnNrUGumZ4NSw5jHRwMwQFfaI9RPX1kSdacJwMqG4pc/2XaGZk416GaYu6SIgVq2oX9LAGkPQ9O8vYam0IbgzQ2CLX1CgNRDT3HglVQWEEEHxQJndVI=; bm_sv=1A2DB7D9781D175C636686F5E01BC2DB~YAAQN16MTxrfHluKAQAAaNj+bhVBxeq5K8l3zXvNUvIosB8DvlVR4NqGVYGfvr8uOVRIykfHTDrXuY+IugODfGFFSs5ANSKZKNQ/bGKr+EuuYzemu1MvN4+4FfYPKm/vRktcygW22xlNa+F8mgyK6d6nauYooXrTI8PwsTEi7pREzxwwY53ymElm+/qWIrOE3FvZq3ohkMFJyiz157/F9AuN0opXxr2ak2PZuquGCZpjwnhfK+HCKqZiFMOZ~1",
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url=url, headers=headers, timeout=10)

    form_links = None
    if response.status_code == 200:
        resss = response.json()
        li = get_def14A_form_link(resss)
        if li["def_14"] and li["k_10"] and li["q_10"] and li["k_8"]:
            form_links = li

    return form_links


def get_def14A_form_link(response):

    form_type_list = response["filings"]["recent"]["form"]

    links = {"def_14": "", "k_10": "", "q_10": "", "k_8": ""}

    cik = response["cik"]

    if "DEF 14A" in form_type_list:
        form_idx = form_type_list.index("DEF 14A")
        accession_number = response["filings"]["recent"]["accessionNumber"][form_idx]
        primary_document = response["filings"]["recent"]["primaryDocument"][form_idx]
        accession_number = accession_number.replace("-", "")
        cik = str("0" * (10 - len(cik))) + cik
        form_link = f"www.sec.gov/Archives/edgar/data/{cik}/{accession_number}/{primary_document}"
        links["def_14"] = form_link
        return links

    if "10-K" in form_type_list:
        form_idx = form_type_list.index("10-K")
        accession_number = response["filings"]["recent"]["accessionNumber"][form_idx]
        primary_document = response["filings"]["recent"]["primaryDocument"][form_idx]
        accession_number = accession_number.replace("-", "")
        cik = str("0" * (10 - len(cik))) + cik
        form_link = f"www.sec.gov/Archives/edgar/data/{cik}/{accession_number}/{primary_document}"
        links["k_10"] = form_link

    if "10-Q" in form_type_list:
        form_idx = form_type_list.index("10-Q")
        accession_number = response["filings"]["recent"]["accessionNumber"][form_idx]
        primary_document = response["filings"]["recent"]["primaryDocument"][form_idx]
        accession_number = accession_number.replace("-", "")
        cik = str("0" * (10 - len(cik))) + cik
        form_link = f"www.sec.gov/Archives/edgar/data/{cik}/{accession_number}/{primary_document}"
        links["q_10"] = form_link

    if "8-K" in form_type_list:
        form_idx = form_type_list.index("8-K")
        accession_number = response["filings"]["recent"]["accessionNumber"][form_idx]
        primary_document = response["filings"]["recent"]["primaryDocument"][form_idx]
        accession_number = accession_number.replace("-", "")
        cik = str("0" * (10 - len(cik))) + cik
        form_link = f"www.sec.gov/Archives/edgar/data/{cik}/{accession_number}/{primary_document}"
        links["k_8"] = form_link

    return links


async def get_profile_info_from_search(company):
    """
    Retrieves the profile name and company name from a search on salary.com.

    Args:
        name (str): The name of the person to search for.
        company (str): The name of the company to search for.

    Returns:
        tuple: A tuple containing the profile name and company name.

    """
    company = company.lower()
    search_term = f"{company}"
    search_term = quote_plus(search_term)
    search_url = (
        f"https://www1.salary.com/Executive-Salaries-Search-Result.html?q={search_term}"
    )

    max_retries = 5
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url=search_url, timeout=15)
                break  # Exit loop if successful
        except Exception as e:
            print("Exception: ", e)
            if attempt < max_retries - 1:  # Only retry if more attempts are left
                await asyncio.sleep(
                    2**attempt
                )  # Exponential backoff: 1, 2, 4, 8 seconds
            else:
                raise e
    soup = BeautifulSoup(response.text, "html.parser")
    a_tags = soup.find_all("td")
    single_company_tag = None
    for td in a_tags:
        if len(td.find_all("span")) == 1:
            single_company_tag = td.find_all("span")
            break

    if not single_company_tag:
        return None
    urls = [span.find("a")["href"] for span in single_company_tag if span.find("a")]

    pattern = r"\.html$"

    matches = []
    for url in urls:
        if isinstance(url, str):
            txt = re.search(pattern, url)
            if txt:
                matches.append(url)

    profile_url = matches[0]
    url_substrings = profile_url.split("-Salary-Bonus-Stock-Options-for-")
    company_name = url_substrings[-1].replace(".html", "")
    return company_name


async def scrape_person_info(url):
    """
    Scrapes executive compensation data for a given profile, company, and year.

    Args:
        profile_name (str): The name of the executive profile.
        company_name (str): The name of the company.
        year (int): The year for which the compensation data is requested.

    Returns:
        dict: A dictionary containing the scraped compensation data, including base pay, bonus, stock options, and more.
    """
    scrape_url = f"https://www.salary.com" + url

    async with httpx.AsyncClient() as client:
        count = 0
        while True:
            try:
                response = await asyncio.wait_for(
                    client.get(url=scrape_url), timeout=25
                )
                if response.status_code == 200 or count == 5:
                    break
            except:
                pass

            count = count + 1
    soup = BeautifulSoup(response.text, "html.parser")

    compensation_items = soup.find_all(class_="exe-detailinfo-table-item")
    compensation_data = {}
    for item in compensation_items:
        title = item.find(class_="exe-detailinfo-table-item-title")
        value = item.find(class_="exe-detailinfo-table-item-value")

        if title and value:
            compensation_type = title.text.strip()
            compensation_value = value.text.strip()
            compensation_data[compensation_type] = int(
                compensation_value.replace("$", "").replace(",", "")
            )

    data = {}
    data["basePay"] = compensation_data["BASE PAY"]
    data["bonusIncentiveCompensation"] = compensation_data["BONUS + INCENTIVE COMP"]
    data["totalCashCompensation"] = compensation_data["TOTAL CASH COMPENSATION"]
    data["stockAwardValue"] = compensation_data["STOCK AWARD VALUE"]
    data["optionAwardValue"] = compensation_data["OPTION AWARD VALUE"]
    data["totalEquity"] = compensation_data["TOTAL EQUITY"]
    data["totalOther"] = compensation_data["TOTAL OTHER"]
    data["totalCompensation"] = compensation_data["TOTAL COMPENSATION"]
    return data


async def scrape_person_info_new(company_name, year):
    """
    Scrapes executive compensation data for a given profile, company, and year.

    Args:
        profile_name (str): The name of the executive profile.
        company_name (str): The name of the company.
        year (int): The year for which the compensation data is requested.

    Returns:
        dict: A dictionary containing the scraped compensation data, including base pay, bonus, stock options, and more.
    """
    scrape_url = f"https://www.salary.com/tools/executive-compensation-calculator/{company_name}?year={year}&view=table#exe"

    async with httpx.AsyncClient() as client:
        count = 0
        while True:
            try:
                response = await asyncio.wait_for(
                    client.get(url=scrape_url), timeout=25
                )
                if response.status_code == 200 or count == 5:
                    break
            except:
                pass

            count = count + 1
    # print(response.text)
    soup = BeautifulSoup(response.text, "html.parser")

    compensation_items = soup.find_all(
        class_="table sa-table tablesaw-stack table-executive"
    )
    compensation_items = compensation_items[0].find_all("tr")

    flag = True
    all_urls = []
    all_titles = []
    tasks = []
    for item in compensation_items:
        if flag:
            flag = False
            continue

        title = item.find_all(class_="tablesaw-cell-content")
        title = title[1]
        all_titles.append(title.text.strip())

        name = item.find("a")
        url = name["href"]
        all_urls.append(url)
        tasks.append(asyncio.create_task(scrape_person_info(url)))

    ind_results = await asyncio.gather(*tasks)

    result = {}
    for index, dat in enumerate(ind_results):
        try:
            result[all_titles[index]] = dat
        except Exception as ex:
            print(ex)
            pass

    return result


async def executive_salary_data(company_name, year):
    """
    Retrieves the salary data for an executive based on their name, company, and year.

    Args:
        personname (str): The name of the executive.
        company (str): The name of the company.
        year (int): The year for which the salary data is requested.

    Returns:
        dict: A dictionary containing the scraped salary data for the executive.

    """
    result = {}
    try:
        executive_salary = await scrape_person_info_new(company_name, str(year))
        for title, value in executive_salary.items():
            if value:
                result.update(
                    {
                        title: {
                            "baseSalary": value.get("basePay", "Not provided"),
                            "equity": value.get("totalEquity", "Not provided"),
                            "nonEquity": value.get("bonusIncentiveCompensation", 0)
                            + value.get("totalOther", 0),
                            "total": value.get("totalCompensation", "Not provided"),
                        }
                    }
                )
    except Exception as ex:
        pass

    return result


def clean_string(input_string):
    for p in string.punctuation:
        input_string = input_string.replace(p, " ")
    input_string = input_string.lower()
    return re.sub(" +", " ", input_string)


# async def format_table_openai(table):
#     # print(table)
#     if not table:
#         return None
#     client = AsyncOpenAI()
#     messages = [
#         {
#             "role": "system",
#             "content": """You are an intelligent assistant. Format the following with relevant column names and rows values. Return a python dictionary object that can be understood. Make sure the years can be understood""",
#         }
#     ]
#     messages.append({"role": "user", "content": str(table)})
#     completion = await client.chat.completions.create(
#         model="gpt-3.5-turbo-0125",
#         messages=messages,
#         temperature=0,  # gpt-3.5-turbo-0125
#     )
#     # print("\n\nWOWWWWW:\n", dict(dict(dict(completion)["choices"][0])["message"])["content"], "\n\n")
#     return dict(dict(dict(completion)["choices"][0])["message"])["content"]


# async def calculated_salary(table):
#     # print(table)
#     if not table:
#         return None
#     client = AsyncOpenAI()
#     messages = [
#         {
#             "role": "system",
#             "content": """You are an intelligent assistant. You will be provided an object with financial information, out of which you have to return the values of 'Base Salary', 'Equity', 'Non-Equity' and 'Total' of each individual.

#             Take a deep breath and undertand: Base salary will ONLY include the base salary. The 'Equity' will include stock and option awards ONLY!!. OPTION AWARDS ARE TO BE INCLUDED IN EQUITY!!!!!!. Non-Equity would be any compensation not included in base salary or equity. All other, extra, non-equity compensation will come in Non-Equity. The total will be the total compensation paid.

#             Remember, you have to add the relevant values in equity and non-equity YOURSELF.
#             Return ONLY in the following format:
#             {
#                 'Year' : {
#                     'Title' : {
#                         'Name' : name-of-person
#                         'Base Salary' : added-numeric-value,
#                         'Equity' : added-numeric-value,
#                         'Non-Equity' : added-numeric-value
#                         'Total' : added-numeric-value
#                         }
#                     }
#             }

#             Instructions: Use the table to fill the keys above. DO NOT REUSE THE VALUES GIVEN AS EXAMPLE. MAKE SURE that the addition of 'Base Salary', 'Equity' and 'Non-Equity' values should be equal to 'Total' value. The 'Title' will be the title of the individual
#             IMPORTANT: DO NOT ADD ANY OTHER TEXT
#             """,
#         }
#     ]
#     messages.append({"role": "user", "content": str(table)})
#     completion = await client.chat.completions.create(
#         model="gpt-3.5-turbo-0125",
#         messages=messages,
#         temperature=0,  # gpt-3.5-turbo-0125
#     )
#     return dict(dict(dict(completion)["choices"][0])["message"])[
#         "content"
#     ]  # "gpt-3.5-turbo-0125"


async def names_same_or_not(company1, company2):
    messages = [
        {
            "role": "system",
            "content": """
                You are an intelligent assistant whose job is to tell whether two company names given to you are same. You have see whether one name can be an abbreviation or a different spelling for the SAME COMPANY.

                Examples:
                Company Names: Microsoft and Microsoft Corporations
                Output: YES

                Company Names: IBM and International Business Machine Corporation
                Output: YES

                Company Names: OpenAI and Qlu.ai
                Output: NO

                Instructions: DO NOT ADD ANY OTHER TEXT OTHER THAN 'YES' OR 'NO'.
            """,
        }
    ]
    messages.append(
        {"role": "user", "content": f"Company Names: {company1} and {company2}"}
    )

    completion = await invoke(
        messages=messages,
        temperature=0,
        model="openai/gpt-4o-mini",
        fallbacks=["anthropic/claude-3-5-haiku-latest"],
    )
    return completion


async def executive_salaries_company(company, universalName, connection, CACHE=True):
    if CACHE == True:
        try:
            check_cache = await get_cached_data(universalName + title_in_table, table)
            if check_cache:
                return check_cache
        except:
            pass

    """
    Retrieves the executive salaries for a given person and company for the years 2020 to 2023.

    Args:
        personname (str): The name of the person.
        company (str): The name of the company.

    Returns:
        dict: A dictionary containing the executive salaries for each year from 2021 to 2023.
    """

    response = await connection.search(
        index=os.getenv("ES_COMPANIES_INDEX"),
        body={"query": {"term": {"li_universalname": {"value": universalName}}}},
    )
    if len(response["hits"]["hits"]) > 0:
        response = response["hits"]["hits"][0]["_source"]
        if (
            "yf_market" in response
            and response["yf_market"]
            and "longname" in response["yf_market"][0]
            and response["yf_market"][0]["longname"]
        ):
            company = response["yf_market"][0]["longname"]
        else:
            company = (
                response["li_name"]
                if response.get("li_name", None)
                else response.get("cb_organization_name", None)
            )

    if not company:
        return None

    company_name = await get_profile_info_from_search(company)
    if not company_name:
        return None
    same = await names_same_or_not(
        company, company_name.replace("-Executive-Salaries", "")
    )

    if "no" in same.lower():
        return None
    salary_data = {}
    tasks = {}
    for year in range(2019, datetime.now().year):
        tasks[year] = asyncio.create_task(executive_salary_data(company_name, year))

    for year, task in tasks.items():
        salary_data[year] = await task

    try:
        await cache_data(universalName + title_in_table, salary_data, table)
    except:
        pass

    return salary_data
