import re
import os
import httpx
import random
import asyncio
import string
from datetime import datetime

from qutils.llm.asynchronous import invoke

from bs4 import BeautifulSoup

from urllib.parse import quote_plus, unquote_plus
from app.core.database import cache_data, get_cached_data, postgres_fetch
from qutils.websearch.websearch import search_google


title_in_table = "~formlinks@"
table = "cache_salary_sec"

title_for_both_in_table = "~person_individual_details_0302@"


async def search_cik(symbol):
    result = await postgres_fetch(
        f"""
            SELECT cik from StocksCiks where stocksymbol = '{symbol}';
        """
    )
    return result


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


async def sec_url_scraping(universalName, connection, CACHE=True):
    if CACHE == True:
        try:
            check_cache = await get_cached_data(universalName + title_in_table, table)
            if check_cache:
                return check_cache
        except:
            pass
    response = await connection.search(
        index=os.getenv("ES_COMPANIES_INDEX"),
        body={"query": {"term": {"li_universalname": {"value": universalName}}}},
    )
    response = (
        response["hits"]["hits"][0]["_source"]
        if response["hits"]["total"]["value"] > 0
        else None
    )

    if not response:
        return {"message": "company not found"}

    tasks = []

    stock_symbol = (
        response["cb_stock_symbol"]
        if "cb_stock_symbol" in response and response["cb_stock_symbol"]
        else ""
    )
    cik_id = None
    if stock_symbol:
        get_cik = await search_cik(stock_symbol)
        if get_cik:
            cik_id = get_cik[0]
        if not cik_id:
            tasks.append(fetch_cik_id_from_index(stock_symbol))

    if not cik_id:
        company_name = response["li_name"]

        if (
            "yf_market" in response
            and response["yf_market"]
            and "longname" in response["yf_market"]
            and response["yf_market"]["longname"]
        ):
            company_name = response["yf_market"]["longname"]

        tasks.append(fetch_cik_id_from_index(company_name))

        results = await asyncio.gather(*tasks)
        for result in results:
            if result:
                cik_id = result
                break

    if cik_id:
        form_links = await fetch_company_data_from_SEC_ES(cik_id)
        if form_links:
            if CACHE == True:
                try:
                    await cache_data(universalName + title_in_table, form_links, table)
                except:
                    pass
            return form_links
        else:
            return {"message": "No form links found for the company"}
    else:
        return {"message": "No CIK ID found for the company"}


async def fetch_cik_id_from_index(search_term):
    await asyncio.sleep(random.uniform(1.2, 1.7))
    url = f"https://efts.sec.gov/LATEST/search-index?keysTyped={search_term}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, timeout=25)
        if response.status_code == 200:
            result = response.json()["hits"]["hits"]
            if len(result) > 0:
                cik_id = result[0]["_id"]
            else:
                cik_id = None
        else:
            cik_id = None
        return cik_id


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
        response = await client.get(url=url, headers=headers, timeout=100)

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


async def get_profile_info_from_search(name, company):
    """
    Retrieves the profile name and company name from a search on salary.com.

    Args:
        name (str): The name of the person to search for.
        company (str): The name of the company to search for.

    Returns:
        tuple: A tuple containing the profile name and company name.

    """
    name = name.lower()
    company = company.lower()
    search_term = f"{name} {company}"
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
    a_tags = soup.find_all("a")
    urls = []
    for a_tag in a_tags:
        urls.append(a_tag.get("href"))
    pattern = r"\.html$"

    matches = []
    for url in urls:
        if isinstance(url, str):
            txt = re.search(pattern, url)
            if txt:
                matches.append(url)

    profile_url = matches[0]
    url_substrings = profile_url.split("-Salary-Bonus-Stock-Options-for-")
    profile_name = url_substrings[0]
    company_name = url_substrings[-1].replace(".html", "")
    return profile_name, company_name


async def scrape_person_info(profile_name, company_name, year):
    """
    Scrapes executive compensation data for a given profile, company, and year.

    Args:
        profile_name (str): The name of the executive profile.
        company_name (str): The name of the company.
        year (int): The year for which the compensation data is requested.

    Returns:
        dict: A dictionary containing the scraped compensation data, including base pay, bonus, stock options, and more.
    """
    scrape_url = f"https://www.salary.com/tools/executive-compensation-calculator/{profile_name}-salary-bonus-stock-options-for-{company_name}?year={year}"

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


async def executive_salary_data(profile_name, company_name, year):
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
        result = await scrape_person_info(profile_name, company_name, str(year))
    except Exception as ex:
        print(ex)
        pass

    return result


def clean_string(input_string):
    for p in string.punctuation:
        input_string = input_string.replace(p, " ")
    input_string = input_string.lower()
    return re.sub(" +", " ", input_string)


async def names_same_or_not(name1, name2, company1, company2):
    messages = [
        {
            "role": "system",
            "content": """
    You are an intelligent assistant tasked with determining whether two human names and two company names are the same.

    You have to answer the given Key Questions about the data.
    ### Key Questions
    1. Can the two human names refer to the same person?
    2. Can the two company names refer to the same company?

    ### Output
    - Return 'YES', if both pairs refer to the same person and company.
    - Return 'NO', otherwise.

    ### Considerations
    - Spelling and style variations are acceptable; focus on whether they could refer to the same entities.
    - One name or company can be an abbreviation of the other.

    ### Examples
    - Human Names: A. Krishna and Arvind Krishna, Company Names: IBM and International Business Machine Corporation
        Output: YES

    - Human Names: Ashish Krishna and Arvind Krishna, Company Names: IBM and International Business Machine Corporation
        Output: NO

    - Human Names: Ahmed Khan and Ahmed Khan, Company Names: Turkey Hill and Beverley Hill
        Output: NO

    - Human Names: Steve Griffins and John Kransk, Company Names: Amazon and Amazon
        Output: NO

    - Human Names: Jeffrey Bezos and Jeff Bezos, Company Names: Amazon and AmazonINC
        Output: YES

    ### Instructions:
    - DO NOT ADD ANY OTHER TEXT OTHER THAN 'YES' OR 'NO'. 
    - Take a deep breath and understand. 
    - Return 'YES' ONLY if its the same person from the same company.
   
    """,
        }
    ]
    messages.append(
        {
            "role": "user",
            "content": f"Human Names: {name1} and {name2}, Company Names: {company1} and {company2}",
        }
    )

    completion = await invoke(
        messages=messages,
        model="openai/gpt-4o-mini",
        temperature=0,
        fallbacks=["anthropic/claude-3-5-haiku-latest"],
    )
    return completion


async def executive_salaries(
    personname, company, universalName, connection, CACHE=True
):
    if CACHE == True:
        try:
            check_cache = await get_cached_data(
                universalName + personname + title_for_both_in_table, table
            )
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

    if universalName:
        response = await connection.search(
            index=os.getenv("ES_COMPANIES_INDEX"),
            body={"query": {"term": {"li_universalname": {"value": universalName}}}},
        )
        if (
            "yf_market" in response
            and response["yf_market"]
            and "longname" in response["yf_market"]
            and response["yf_market"]["longname"]
        ):
            company = response["yf_market"]["longname"]

    profile_name, company_name = await get_profile_info_from_search(personname, company)

    profile_name2 = (
        profile_name.replace("-", " ")
        .translate(str.maketrans("", "", string.punctuation))
        .lower()
    )
    personname = personname.translate(str.maketrans("", "", string.punctuation)).lower()

    same = await names_same_or_not(profile_name2, personname, company, company_name)
    if "no" in same.lower():
        return None

    salary_data = {}
    tasks = {}
    for year in range(2019, datetime.now().year):
        tasks[year] = asyncio.create_task(
            executive_salary_data(profile_name, company_name, year)
        )

    for year, task in tasks.items():
        salary_data[year] = await task

    task2 = asyncio.create_task(sec_url_scraping(universalName, connection))

    def14A_link = await task2
    try:
        await cache_data(
            universalName + personname + title_for_both_in_table,
            (salary_data, def14A_link),
            table,
        )
    except:
        pass
    return salary_data, def14A_link
