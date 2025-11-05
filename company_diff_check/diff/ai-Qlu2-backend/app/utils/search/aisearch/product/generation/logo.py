import os
import json
import httpx
import base64
import asyncio
import aiohttp
import textwrap
from PIL import Image
from io import BytesIO
from bs4 import BeautifulSoup
from collections import Counter

from qutils.llm.asynchronous import invoke

try:
    resample_filter = Image.Resampling.LANCZOS
except AttributeError:
    resample_filter = Image.ANTIALIAS

from google.cloud import storage
from google.oauth2 import service_account

bucket_name = os.getenv("PRODUCT_LOGO_BUCKET")


def post_process_gpt_output(response):
    return (
        response[response[: response.rfind("<")].rfind("<") :]
        .split("<")[1]
        .split(">")[1]
        .strip()
    )


async def check_uniqueness_of_products(companyname, product_name):
    user_message = f"""
        <Task>
        Find the uniqueness of the {product_name} for the given company {companyname}. The goal is to identify whether the product can be easily distinguished from other products in the market without needing the company name. Ensure that the product name is unique enough to search for its logo directly on the internet.
        </Task>

        <Instruction>
        - If the product name is unique enough on its own to be identified and distinguishable in the market, return only the product name.
        - If the product name is generic or not sufficiently unique, append the company name to make it distinguishable. 
        - If the company name is already part of the product name, check whether it can be removed without losing uniqueness. If removing it makes the product name too generic or ambiguous, keep the company name.
        - The returned product name should be unique enough to reliably find the product logo online through a search.
        - In case of products which occcur in multiple companies, the company name should be included in the product name. So, the product name should be unique enough to be distinguished from other products of the same name.
        </Instruction>

        <Example>
            User: Apple iPhone
            Response: iPhone

            User: Google Search
            Response: Google Search
        </Example>

        <Response>
            You must return the response enclosed in <output></output> tag. e.g. <output>Youtube</output>   
        </Response>
            """

    system = """Your name is Jared and you are an expert in finding the uniqueness of the products name of a company."""
    response = await invoke(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
        temperature=0,
        model="openai/gpt-4.1",
        fallbacks=["anthropic/claude-sonnet-4-latest"],
    )
    return post_process_gpt_output(response)


def json_to_base64(data):
    json_str = json.dumps(data)
    base64_bytes = base64.b64encode(json_str.encode("utf-8"))
    base64_str = base64_bytes.decode("utf-8")
    return base64_str


async def get_from_pegasus(function):
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.get(
                url=os.getenv("CLOUDFUNCTION_SERVICE"),
                headers={"accept": "application/json"},
                params={"custom_function": function},
            )
            response.raise_for_status()
            json_response = response.json()
            return json_response
        except Exception as exception:
            print(exception)
            return None


async def parse_google_images(html):
    """Parse the HTML of the Google Images search results page to extract image URLs"""
    soup = BeautifulSoup(html, "html.parser")
    image_urls = []

    for img in soup.find_all("img"):
        src = img.get("src")
        if src and "/images/branding/searchlogo" not in src:
            image_urls.append(src)

    return image_urls


async def get_product_image(company, product, max_retries=3, base_delay=1.0):
    try:
        result = await check_uniqueness_of_products(company, product)
        query = result + " logo"

        # Add retry logic specifically for pegasus request
        pegasus_response = None
        for attempt in range(max_retries + 1):
            try:
                pegasus_response = await get_from_pegasus(
                    json_to_base64(
                        {
                            "custom_function": {
                                "code": textwrap.dedent(
                                    f"""
                import os
                import requests

                os.environ.pop("HTTP_PROXY", None)
                os.environ.pop("HTTPS_PROXY", None)
                os.environ.pop("http_proxy", None)
                os.environ.pop("https_proxy", None)

                headers = {{
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)",
                    "Accept-Encoding": "gzip",
                }}

                search_term = '{query}'

                try:
                    response = requests.get(
                        "https://www.google.com/search", 
                        params={{'q': search_term, 'tbm': 'isch'}}, 
                        headers=headers, 
                        timeout=60
                    )
                    
                    if response.status_code == 200:
                        result = response.text
                    else:
                        result = None
                except Exception as e:
                    print(f"Request failed: {{e}}")
                    result = None
                """
                                ),
                                "imports": [
                                    "os",
                                    "requests",
                                ],
                            }
                        }
                    )
                )
                break  # If successful, exit retry loop
            except Exception as e:
                if attempt < max_retries:
                    delay = base_delay * (2**attempt)
                    print(
                        f"Pegasus request attempt {attempt + 1} failed. Error: {e}. "
                        f"Retrying in {delay} seconds..."
                    )
                    await asyncio.sleep(delay)
                else:
                    print(f"Final pegasus request attempt failed. Error: {e}")
                    return None

        if not pegasus_response:
            return None

        html = pegasus_response["code_result"]["result"]
        image_urls = await parse_google_images(html)
        if image_urls:
            return image_urls[0]
        else:
            return None
    except:
        return None


def image_to_base64(image):
    if not image:
        return None
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    buffered.seek(0)
    img_bytes = buffered.getvalue()
    img_base64 = base64.b64encode(img_bytes).decode("utf-8")
    return img_base64


def get_dominant_color(image, k=1):
    small_image = image.resize((50, 50))
    pixels = list(small_image.getdata())
    counter = Counter(pixels)
    most_common_colors = counter.most_common(k)

    return most_common_colors[0][0] if most_common_colors else (255, 255, 255, 255)


async def download_and_resize_image(
    session, url, icon_size, max_retries=3, base_delay=1
):
    for attempt in range(max_retries + 1):
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    img = Image.open(BytesIO(image_data)).convert("RGBA")
                    dominant_color = get_dominant_color(img)
                    img.thumbnail(icon_size, resample=resample_filter)

                    new_img = Image.new("RGBA", icon_size, dominant_color)

                    x = (icon_size[0] - img.size[0]) // 2
                    y = (icon_size[1] - img.size[1]) // 2

                    new_img.paste(img, (x, y), img)
                    return new_img
                else:
                    if attempt < max_retries:
                        delay = base_delay * (2 * attempt)  # Exponential backoff
                        print(
                            f"Attempt {attempt + 1} failed for {url}. Status: {response.status}. "
                            f"Retrying in {delay} seconds..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        print(
                            f"Final attempt failed for {url}. HTTP status code: {response.status}"
                        )
                        return None

        except Exception as e:
            if attempt < max_retries:
                delay = base_delay * (2**attempt)
                print(
                    f"Attempt {attempt + 1} failed for {url}. Error: {e}. "
                    f"Retrying in {delay} seconds..."
                )
                await asyncio.sleep(delay)
            else:
                print(f"Final attempt failed for {url}. Error: {e}")
                return None
    return None


async def process_images_to_base64(urls, icon_size):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for idx, url in enumerate(urls):
            tasks.append(download_and_resize_image(session, url, icon_size))

        results = await asyncio.gather(*tasks)
        encoded_images = [image_to_base64(img) for img in results]
        return encoded_images


async def upload_to_bucket(bucket_name, image, unique_id):
    GOOGLE_APPLICATION_CREDENTIALS = {
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
    filename = f"{unique_id}.png"

    img_byte_arr = BytesIO()
    image.save(img_byte_arr, format="PNG")
    img_byte_arr.seek(0)

    credentials = service_account.Credentials.from_service_account_info(
        GOOGLE_APPLICATION_CREDENTIALS
    )
    storage_client = storage.Client(credentials=credentials)

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(f"images/{filename}")
    blob.upload_from_file(img_byte_arr, content_type="image/png")
    url = f"https://storage.googleapis.com/{bucket_name}/{blob.name}"
    return url


async def process_images(product_identifier, urls, icon_size):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for idx, url in enumerate(urls):
            tasks.append(download_and_resize_image(session, url, icon_size))
            break

        results = await asyncio.gather(*tasks)
        upload_tasks = []
        for idx, img in enumerate(results):
            if img:
                upload_tasks.append(
                    upload_to_bucket(bucket_name, img, f"{product_identifier}")
                )

        public_urls = await asyncio.gather(*upload_tasks)
        return public_urls
