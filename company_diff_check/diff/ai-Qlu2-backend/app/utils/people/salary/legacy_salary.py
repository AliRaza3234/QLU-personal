import re
import os
import httpx
import random
import asyncio
import string
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import quote_plus, unquote_plus
from qutils.websearch.websearch import search_google
from app.core.database import cache_data, get_cached_data


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


async def sec_url_scraping(universalName, client, CACHE=True):
    if CACHE == True:
        try:
            check_cache = await get_cached_data(
                universalName + "~formlinks@", "cache_salary_sec"
            )
            if check_cache:
                return check_cache
        except:
            pass
    response = await client.search(
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

    stock_symbol = (
        response["cb_stock_symbol"]
        if "cb_stock_symbol" in response and response["cb_stock_symbol"]
        else ""
    )

    company_name = response["li_name"]

    cik_id = None
    if stock_symbol:
        cik_id = await fetch_cik_id_from_stock_symbol(stock_symbol)

    if not cik_id:
        cik_id = await fetch_cik_id_from_li_name(company_name)

    if cik_id:
        form_links = await fetch_company_data_from_SEC_ES(cik_id)
        if form_links:
            if CACHE == True:
                try:
                    await cache_data(
                        universalName + "~formlinks@", form_links, "cache_salary_sec"
                    )
                except:
                    pass
            return form_links
        else:
            return {"message": "No form links found for the company"}
    else:
        return {"message": "No CIK ID found for the company"}


async def fetch_cik_id_from_stock_symbol(search_term):
    url = "https://efts.sec.gov/LATEST/search-index"

    payload = {"category": "custom", "entityName": search_term, "forms": "10-K"}
    headers = {
        "Content-Type": "application/json",
        "Cookie": "ak_bmsc=17FA57B64D6E503D6E5CC7A90B696960~000000000000000000000000000000~YAAQN16MT5pAHluKAQAAi+z9bRXMm9aXZS/T82aasTIpOr2rPuak7wpga/o9/krowKEMirnutYSYHY+rluq4QUtA/Z48SW1rncK1vaTrccPXunz4BAC9R4MUVa4wubvyraF4IoUnQrWi+HAHZYVALzzLvuS3Dm7xbGM2QVLgK5UPOUziNxaA/DOTnj04uWJPQRAsMadxCy1xKfSlTXXl34lrR26bQdRN6MwxzexxKzpDUYKPmF3K/kEAT/vkdvIiqs4kAzcOnVhRoA+9moIV9dNnitdwxFpRoslzC+IcN53ultTO7ks9zmNt0w41ejaYuoccaJISN9CoJttmj78UQYGPh/D/1wyuB+kONM2B383DaQhZpAwFEpk=; bm_sv=59E9E5CEFC8357FBD2ADC31E7873D5A3~YAAQN16MT+9RHluKAQAAtLc1bhUoiSECRGuGBI4iA2v3E2xHP+OBIZ3/6sQMGsOPkOGKjmz3haeB/EXrrgQ5Zo6hgNtGISUfE+TCKTDnGwvBaSt5IPvNOCjt/YNH8uEHxCt62uUem2vfk7oLYkk/VWVGykeGLMZNu4JSD0Sj3Cr4ZA1vxkDsOwLZUESX3CVza//0N1C0NwMoi5w1hGTpqLlYUjTjTql/WyhvycapYj4CYVZS3ZtVErfMum55~1",
        "Accept": "*/*",
        "User-Agent": "Thunder Client (https://www.thunderclient.com)",
    }

    cik_id = None

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url=url, params=payload, headers=headers, timeout=10
        )

    if response.status_code == 200:
        result = response.json()["hits"]["hits"]
        if len(result) > 0:
            for i in range(len(result)):
                display_names = result[i]["_source"]["display_names"][0]
                stock_symbol_cik = display_names[display_names.find("(") + 1 :]
                if search_term in stock_symbol_cik:
                    cik_id = result[i]["_source"]["ciks"][0]

                    break

        else:
            cik_id = None
    else:
        cik_id = None

    return cik_id


async def fetch_cik_id_from_li_name(search_term):
    url = "https://efts.sec.gov/LATEST/search-index"

    payload = {"category": "custom", "entityName": search_term, "forms": "10-K"}
    headers = {
        "Content-Type": "application/json",
        "Cookie": "ak_bmsc=17FA57B64D6E503D6E5CC7A90B696960~000000000000000000000000000000~YAAQN16MT5pAHluKAQAAi+z9bRXMm9aXZS/T82aasTIpOr2rPuak7wpga/o9/krowKEMirnutYSYHY+rluq4QUtA/Z48SW1rncK1vaTrccPXunz4BAC9R4MUVa4wubvyraF4IoUnQrWi+HAHZYVALzzLvuS3Dm7xbGM2QVLgK5UPOUziNxaA/DOTnj04uWJPQRAsMadxCy1xKfSlTXXl34lrR26bQdRN6MwxzexxKzpDUYKPmF3K/kEAT/vkdvIiqs4kAzcOnVhRoA+9moIV9dNnitdwxFpRoslzC+IcN53ultTO7ks9zmNt0w41ejaYuoccaJISN9CoJttmj78UQYGPh/D/1wyuB+kONM2B383DaQhZpAwFEpk=; bm_sv=59E9E5CEFC8357FBD2ADC31E7873D5A3~YAAQN16MT+9RHluKAQAAtLc1bhUoiSECRGuGBI4iA2v3E2xHP+OBIZ3/6sQMGsOPkOGKjmz3haeB/EXrrgQ5Zo6hgNtGISUfE+TCKTDnGwvBaSt5IPvNOCjt/YNH8uEHxCt62uUem2vfk7oLYkk/VWVGykeGLMZNu4JSD0Sj3Cr4ZA1vxkDsOwLZUESX3CVza//0N1C0NwMoi5w1hGTpqLlYUjTjTql/WyhvycapYj4CYVZS3ZtVErfMum55~1",
        "Accept": "*/*",
        "User-Agent": "Thunder Client (https://www.thunderclient.com)",
    }

    cik_id = None

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url=url, params=payload, headers=headers, timeout=10
        )

    search_term = search_term.upper()

    if response.status_code == 200:
        result = response.json()["hits"]["hits"]
        if len(result) > 0:
            for i in range(len(result)):
                display_names = result[i]["_source"]["display_names"][0]
                if search_term in display_names:
                    cik_id = result[i]["_source"]["ciks"][0]
                    break

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

    if "10-K" in form_type_list:
        form_idx = form_type_list.index("10-K")
        accession_number = response["filings"]["recent"]["accessionNumber"][form_idx]
        primary_document = response["filings"]["recent"]["primaryDocument"][form_idx]
        accession_number = accession_number.replace("-", "")
        cik = str("0" * (10 - len(cik))) + cik
        form_link = f"www.sec.gov/Archives/edgar/data/{cik}/{accession_number}/{primary_document}"
        links["k_10"] = form_link

    if "10-Q" in form_type_list:
        form_idx_24 = form_type_list.index("10-Q")

        relations = []

        all_10Q_forms = [i for i, x in enumerate(form_type_list) if x == "10-Q"]
        all_10Q_forms = all_10Q_forms[:3]

        form_idx_23 = form_type_list[form_idx_24 + 1 :].index("10-Q")
        form_idx_22 = form_type_list[form_idx_23 + 1 :].index("10-Q")

        accession_number_24 = response["filings"]["recent"]["accessionNumber"][
            all_10Q_forms[0]
        ]
        accession_number_23 = response["filings"]["recent"]["accessionNumber"][
            all_10Q_forms[1]
        ]
        accession_number_22 = response["filings"]["recent"]["accessionNumber"][
            all_10Q_forms[2]
        ]

        primary_document_24 = response["filings"]["recent"]["primaryDocument"][
            all_10Q_forms[0]
        ]
        primary_document_23 = response["filings"]["recent"]["primaryDocument"][
            all_10Q_forms[1]
        ]
        primary_document_22 = response["filings"]["recent"]["primaryDocument"][
            all_10Q_forms[2]
        ]

        accession_number_24 = accession_number_24.replace("-", "")
        accession_number_23 = accession_number_23.replace("-", "")
        accession_number_22 = accession_number_22.replace("-", "")

        cik = str("0" * (10 - len(cik))) + cik

        form_link_24 = f"www.sec.gov/Archives/edgar/data/{cik}/{accession_number_24}/{primary_document_24}"
        form_link_23 = f"www.sec.gov/Archives/edgar/data/{cik}/{accession_number_23}/{primary_document_23}"
        form_link_22 = f"www.sec.gov/Archives/edgar/data/{cik}/{accession_number_22}/{primary_document_22}"

        links["q_10"] = [form_link_24, form_link_23, form_link_22]

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

    async with httpx.AsyncClient() as client:
        response = await client.get(url=search_url, timeout=10)
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
                    client.get(url=scrape_url), timeout=200
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


async def executive_salaries(personname, company, universalName):
    """
    Retrieves the executive salaries for a given person and company for the years 2020 to 2023.

    Args:
        personname (str): The name of the person.
        company (str): The name of the company.

    Returns:
        dict: A dictionary containing the executive salaries for each year from 2021 to 2023.
    """
    profile_name, company_name = await get_profile_info_from_search(personname, company)
    company = company.split(" ")[0]

    if clean_string(company).strip() not in clean_string(company_name).strip():
        return None, None

    profile_name2 = profile_name.split("-")[0]
    personname = personname.split(" ")[0]

    if personname.lower() not in profile_name2.lower():
        return None, None

    salary_data = {}
    tasks = {}
    for year in range(2019, datetime.now().year):
        tasks[year] = asyncio.create_task(
            executive_salary_data(profile_name, company_name, year)
        )

    task2 = asyncio.create_task(sec_url_scraping(universalName))
    for year, task in tasks.items():
        salary_data[year] = await task

    def14A_link = await task2
    return salary_data, def14A_link
