import os
import re
from datetime import datetime
from google.cloud import storage
from google.oauth2 import service_account


async def get_sec_bucket():
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

    return bucket


def extract_date(file_name):
    date_str = file_name.split("/")[2]
    date_str = date_str.split("-")
    cleaned_date = ""
    for i in range(3):
        cleaned_date += date_str[i]
        cleaned_date += "-"
    return datetime.strptime(cleaned_date, "%Y-%m-%d-")


def label_reports_with_quarters(doc_names):

    doc_names = sorted(doc_names, key=extract_date)

    quarter_labelled_docs = {}
    for doc in doc_names:
        temp_month = int(doc.split("/")[2].split("-")[1])

        if temp_month in [1, 2, 3, 4]:
            quarter_labelled_docs[1] = doc
        if temp_month in [5, 6, 7]:
            quarter_labelled_docs[2] = doc
        if temp_month in [8, 9, 10]:
            quarter_labelled_docs[3] = doc
        if temp_month in [11, 12]:
            quarter_labelled_docs[4] = doc

    return quarter_labelled_docs


def generate_all_comma_formats(value):
    str_value = str(value)

    if len(str_value) < 4:
        str_value += "000000"

    str_value = str_value[:4]

    possible_formats = [str_value]
    for i in range(1, len(str_value)):
        temp_number = str_value[:i] + "," + str_value[i:]
        possible_formats.append(temp_number)

    str_value = str_value[:-1]
    for i in range(1, len(str_value)):
        temp_number = str_value[:i] + "," + str_value[i:]
        possible_formats.append(temp_number)

    return possible_formats


def extract_content_from_text(soup, company_name, number):
    million_value = number / 1_000_000
    num_variations = [
        f"{number:,}",
        f"{million_value:.1f} million",
        f"{number}",
    ]

    num_pattern = "|".join(re.escape(variation) for variation in num_variations)
    num_pattern = rf"({num_pattern})"

    paragraphs = soup.find_all("p")

    result_paragraphs = []
    for para in paragraphs:
        para_text = para.get_text()
        lower_company_name = company_name.split(" ")[0]

        if lower_company_name in para_text:

            if re.search(num_pattern, para_text):
                result_paragraphs.append(para_text)

    return result_paragraphs
