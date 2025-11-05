import os
import asyncio
import html2text
from google.cloud import storage
from google.oauth2 import service_account


async def fetch_html_data(url, blob_name):

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
    try:
        storage_client = storage.Client(credentials=credentials)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        data = await asyncio.to_thread(blob.download_as_bytes)
        return data
    except:
        return None


async def get_data(blob_name, url):
    content = await fetch_html_data(url, blob_name)
    if content:
        content = content.decode("utf-8")
        ext = os.path.splitext(blob_name)[1].lower()

        if ext in [".htm", ".html"]:
            text_content = html2text.html2text(content)
            return text_content

        elif ext == ".txt":
            return content
        else:
            print(f"Unsupported file extension: {ext}")
            return None
