import os
import asyncio
from google.cloud import storage
from google.oauth2 import service_account
from app.core.database import postgres_fetch
import time


async def get_sec_doc_from_doc_store(cik):
    bucket_name = os.getenv("SEC_DOC_STORE_BUCKET_NAME")
    service_account_info = {
        "type": "service_account",
        "project_id": os.getenv("GOOGLE_PROJECT_ID"),
        "private_key_id": os.getenv("PRIVATE_KEY_ID"),
        "private_key": os.getenv("PRIVATE_KEY").replace("\\n", "\n"),
        "client_email": os.getenv("CLIENT_EMAIL"),
        "client_id": os.getenv("CLIENT_ID"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": os.getenv("CLIENT_X509_CERT_URL"),
    }

    credentials = service_account.Credentials.from_service_account_info(
        service_account_info
    )
    storage_client = storage.Client(credentials=credentials)
    bucket = storage_client.bucket(bucket_name)

    start_time = time.time()

    print("\t\t", time.time() - start_time, "got bucket")
    start_time = time.time()
    gcs_folder_path = f"{cik}/"
    iterator = await asyncio.to_thread(bucket.list_blobs, prefix=gcs_folder_path)
    blobs = list(iterator)
    print("\t\t", time.time() - start_time, "got blobs against cik")
    if not blobs:
        return {
            "error": "This company hasn't filed any 10-K or 10-Q reports",
            "cik": cik,
        }
    report_data = {}

    start_time = time.time()
    for blob in blobs:
        year = blob.name.split("/")[1]
        if year not in report_data:
            report_data[year] = []
        url = None
        report_data[year].append([blob.name, url])
    print("\t\t", time.time() - start_time, "iterate")
    return report_data


async def label_reports(report_data):
    updated_reports = {}
    for year, reports_list in report_data.items():
        year = int(year)

        updated_reports[year] = {}
        for report_element in reports_list:

            report_name = report_element[0]
            report_link = report_element[1]
            if "10-Q" in report_name:
                label = "Quarterly Financial Report"

                temp_month = int(report_name.split("-")[1])

                if temp_month in [1, 2, 3, 4]:
                    label += " (10-Q1)"
                elif temp_month in [5, 6, 7]:
                    label += " (10-Q2)"
                elif temp_month in [8, 9, 10]:
                    label += " (10-Q3)"
                elif temp_month in [11, 12]:
                    label += " (10-Q4)"

                updated_reports[year][label] = {}
                updated_reports[year][label]["report_link"] = report_link
                updated_reports[year][label]["blob_name"] = report_name

            elif "10-K" in report_name:
                label = "Annual Financial Report (10-K)"
                updated_reports[year][label] = {}
                updated_reports[year][label]["report_link"] = report_link
                updated_reports[year][label]["blob_name"] = report_name

            elif "DEF14" in report_name:
                label = "Definitive Proxy Statement (DEF 14)"
                updated_reports[year][label] = {}
                updated_reports[year][label]["report_link"] = report_link
                updated_reports[year][label]["blob_name"] = report_name
            try:
                filing_date = "-".join(report_name.split("/")[2].split("-")[:3])
                updated_reports[year][label]["filing_date"] = filing_date
            except:
                updated_reports[year][label]["filing_date"] = None

    return updated_reports


async def get_report_data(li_universal_name, client):

    total_start = time.time()
    start_time = time.time()
    es_result = await client.search(
        index=os.getenv("ES_COMPANIES_INDEX"),
        body={
            "_source": ["cb_stock_symbol"],
            "query": {"match_phrase": {"li_universalname": li_universal_name}},
        },
    )
    if (
        len(es_result["hits"]["hits"]) == 0
        or not es_result["hits"]["hits"][0]["_source"]
        or not es_result["hits"]["hits"][0]["_source"]["cb_stock_symbol"]
        or es_result["hits"]["hits"][0]["_source"]["cb_stock_symbol"] == ""
    ):
        return {"error": "Stock Symbol not found for this universal name"}
    duration = time.time() - start_time
    stock_symbol = es_result["hits"]["hits"][0]["_source"]["cb_stock_symbol"]
    print(f"got stock in {duration}")

    start_time = time.time()
    fetch_query = f"""
        SELECT cik FROM stocksciks WHERE stocksymbol = '{stock_symbol}'
    """
    response = await postgres_fetch(fetch_query)
    if response is None:
        return {"error": "CIK not found for this universal name"}
    duration = time.time() - start_time
    cik = response[0]
    print(f"got cik in {duration}")

    start_time = time.time()
    report_data = await get_sec_doc_from_doc_store(cik)
    duration = time.time() - start_time
    print(f"got raw reports in {duration}")
    if "error" in report_data:
        return report_data
    start_time = time.time()
    labelled_report_data = await label_reports(report_data)
    duration = time.time() - start_time
    print(f"got labelled reports in {duration}")
    labelled_report_data = {
        year: dict(
            sorted(
                labelled_report_data[year].items(),
                key=lambda item: item[1]["filing_date"],
                reverse=True,
            )
        )
        for year in labelled_report_data
    }

    print("total exec:", time.time() - total_start)

    return labelled_report_data
