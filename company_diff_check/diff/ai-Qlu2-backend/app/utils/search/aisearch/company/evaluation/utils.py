import os
import httpx
import logging
import random
import asyncio
import traceback
import urllib.parse
from fuzzysearch import find_near_matches
from app.core.database import cache_data, get_cached_data


def split_lists(data):
    try:
        if not data:
            return []

        sub_list_length = len(data[0])
        if any(len(sub_list) != sub_list_length for sub_list in data):
            raise ValueError("All sub-lists must have the same length")

        transposed_data = list(zip(*data))

        result = [list(item) for item in transposed_data]

        return result
    except:
        traceback.print_exc()


async def cache_search_results(query, response):
    if query and query.strip():
        try:
            return await cache_data(query, response, "cache_web_index")
        except Exception as e:
            print("Exception:", e)
    else:
        print("Query is empty or contains only whitespace. Skipping caching.")


async def get_cache_search_results(query):
    try:
        return await get_cached_data(query, "cache_web_index")
    except Exception as e:
        print("Exception: ", e)


async def proxy_inference(prompt):
    url = os.getenv("CLOUDFUNCTION_SERVICE")
    headers = {"accept": "application/json"}
    params = {"query": prompt}

    max_retries = 5
    base_delay = 1

    async with httpx.AsyncClient(timeout=60) as client:
        for attempt in range(1, max_retries + 1):
            try:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                json_response = response.json()
                if "error" in json_response:
                    raise ValueError(f"Error in response: {json_response['error']}")
                return json_response

            except httpx.HTTPStatusError as http_err:
                logging.error(
                    f"Attempt {attempt}: HTTP error {http_err.response.status_code}. Retrying..."
                )
            except httpx.RequestError as req_err:
                logging.error(
                    f"Attempt {attempt}: Request error occurred: {req_err}. Retrying..."
                )
            except ValueError as val_err:
                logging.error(
                    f"Attempt {attempt}: Value error occurred: {val_err}. Retrying..."
                )
            except Exception as e:
                logging.error(
                    f"Attempt {attempt}: Unexpected exception: {e}. Retrying..."
                )

            retry_delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            if attempt < max_retries:
                logging.info(f"Retrying after {retry_delay:.2f} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                logging.error(
                    f"Max retries reached. Failed to get response for prompt: {prompt}"
                )
                break

    return None


def extract_and_decode_url(encoded_url):
    parts = encoded_url.split("/")

    for part in parts:
        if part.startswith("RU="):
            encoded_part = part[3:]
            decoded_url = urllib.parse.unquote(encoded_part)
            return decoded_url

    return "Invalid URL"


def verify_substring_index(main_string, substring):
    matches = find_near_matches(substring.lower(), main_string.lower(), max_l_dist=4)
    if matches:
        matched_text = main_string[matches[0].start : matches[0].end]
        index = [
            main_string.find(matched_text),
            (main_string.find(matched_text) + len(substring) - 1),
        ]
        return index
    else:
        return None
