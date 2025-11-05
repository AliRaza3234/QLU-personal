import os
import json
import httpx
import urllib
import asyncio
from qutils.llm.asynchronous import invoke
from app.utils.search.aisearch.company.generation.mapping import white_death
from app.utils.search.aisearch.company.generation.utilities import (
    post_process_gpt_output,
)


async def industry_generator(prompt):
    user_prompt = f"""
            <Task>
                - Based on the user query: "{prompt}" give me a list of industries that would be relevant for finding such companies.
                - Make sure to only generate 1 to 3 industries which are the most relevant to look at.
                - The amount is dependant on the open ended nature of the query, if more are required to cover the query you may generate more.
                - If only a company is mentioned that you dont know in the prompt, return an empty list.
            </Task>

            <Output>
                - First give your thought process in one line then give the list of industries.
                - Give your output in the form <prediction>["industry 1", "industry 2", ...]</prediction>.
            </Output>
        """

    response = await invoke(
        model="groq/llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "You are a relevant industry name generating agent.",
            },
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        fallbacks=["openai/gpt-4.1"],
    )

    return post_process_gpt_output(response)


def extract_and_decode_url(encoded_url):
    parts = encoded_url.split("/")
    for part in parts:
        if part.startswith("RU="):
            encoded_part = part[3:]
            decoded_url = urllib.parse.unquote(encoded_part)
            return decoded_url
    return "Invalid URL"


async def get_from_pegasus(prompt):
    url = os.getenv("CLOUDFUNCTION_SERVICE")
    headers = {"accept": "application/json"}
    search_engines = ["google", "yahoo"]
    retries = 3
    delay = 1.5

    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(retries):
            for search_engine in search_engines:
                params = {"query": prompt, "search_engine": search_engine}
                try:
                    response = await client.get(url, headers=headers, params=params)
                    response.raise_for_status()
                    json_response = response.json()
                    return json_response
                except httpx.HTTPStatusError as http_err:
                    status_code = http_err.response.status_code
                    print(
                        f"Attempt {attempt + 1} - Status code: {status_code} with search engine {search_engine}"
                    )
                except httpx.RequestError as req_err:
                    print(
                        f"Attempt {attempt + 1} - Request error occurred: {str(req_err)} with search engine {search_engine}"
                    )
                except json.JSONDecodeError as json_err:
                    print(
                        f"Attempt {attempt + 1} - JSON decode error occurred: {str(json_err)} with search engine {search_engine}"
                    )
                except Exception as e:
                    print(
                        f"Attempt {attempt + 1} - Exception: {e} with search engine {search_engine}"
                    )

                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                else:
                    break

    return None


async def get_linkedin_identifier(
    company_name, industry, client, hashmap_companies=None
):
    try:
        if industry:
            prompt = company_name
            result = await white_death(
                prompt,
                company_name,
                industry,
                client,
                company_mapping_cache=hashmap_companies,
            )
            if result:
                li_name = result[1]["li_universalname"]
            else:
                return None
            return li_name
        else:
            search_term = f"LinkedIn page of company: {company_name}"
            google_response = await get_from_pegasus(search_term)
            search_engine = google_response["search_engine"]
            li_name = None
            if google_response and "query_result" in google_response:
                response = google_response

                for element in response.get("query_result"):
                    link_extracted = element["link"]
                    if search_engine == "yahoo":
                        link_extracted = extract_and_decode_url(link_extracted)
                    if "linkedin.com/company" in link_extracted:
                        li_name = link_extracted.split("/company/")[-1].split("/")[0]
                        if "?" in li_name:
                            li_name = li_name.split("?")[0]
                        return li_name
                return li_name

    except:
        search_term = f"LinkedIn page of company: {company_name}"
        google_response = await get_from_pegasus(search_term)
        search_engine = google_response["search_engine"]
        li_name = None
        if google_response and "query_result" in google_response:
            response = google_response

            for element in response.get("query_result"):
                link_extracted = element["link"]
                if search_engine == "yahoo":
                    link_extracted = extract_and_decode_url(link_extracted)
                if "linkedin.com/company" in link_extracted:
                    li_name = link_extracted.split("/company/")[-1].split("/")[0]
                    if "?" in li_name:
                        li_name = li_name.split("?")[0]
                    return li_name

            return li_name
