import os
import json
import httpx
import random
import asyncio
import logging
import datetime
import tldextract
import numpy as np
from itertools import product
from urllib.parse import unquote

from app.core.database import postgres_fetch, postgres_insert
from app.utils.people.salary.person_salary import main as all_title_salary_final
from app.utils.search.qsearch.tmap.glassdoor import get_glassdoor_salary

from qutils.llm.asynchronous import invoke


async def insert_into_cache_talent_map_salary(key_data, value_data):
    key_json = json.dumps(key_data)
    value_json = json.dumps(value_data)
    query = f"""
        INSERT INTO cache_talent_map_salary (key, value)
        VALUES ('{key_json}'::jsonb, '{value_json}'::jsonb)
    """

    await postgres_insert(query)


async def fetch_value_by_key(key_data):
    key_json = json.dumps(key_data)

    query = f"""
        SELECT value, created_at
        FROM cache_talent_map_salary
        WHERE jsonb_array_length(key) = {len(key_data)}
        AND key @> '{key_json}'::jsonb
    """

    result = await postgres_fetch(query)

    if not result:
        return None

    value, created_at = result
    if created_at < (datetime.datetime.now() - datetime.timedelta(days=3)):
        delete_query = f"""
            DELETE FROM cache_talent_map_salary
            WHERE jsonb_array_length(key) = {len(key_data)}
            AND key @> '{key_json}'::jsonb
        """
        await postgres_insert(delete_query)
        return None

    return value


async def search_cik(symbol):
    if symbol.lower() == "usd":
        return 1
    result = await postgres_fetch(
        f"""
            SELECT exchange_rate from cache_exchange_rate where currency = '{symbol}';
        """
    )
    if result:
        return result[0]
    else:
        return 1


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


async def average_pay_snippets(prompt, information):

    system_prompt = f"""
    You are an intelligent assistant tasked with determining the {prompt} using ONLY the information provided to you.
    """

    user_prompt = f"""
    <Instructions>

        - You have to determine the {prompt} using ONLY the information provided to you ahead. Focus more on the information from sites such as Glassdoor, Salary, Indeed.
        - The average salary should be YEARLY. If data ONLY pertains to hourly or monthly salaries, calculate the yearly salary and return that.
        - Return a minimum average, an average and a maximum average in your output. Return this output as a json object in <Output></Output> XML tags.

        Take a deep breath and understand:
        The "minimum average" and "maximum average" are not the absolute minimum or maximum salaries reported. Instead, they represent lower and upper bounds on the average salary, respectively. For instance, the minimum average could be an estimate of the lowest range of expected averages in a specific category (like entry-level roles), while the maximum average could represent the highest expected average for more experienced or specialized positions.

    </Instructions>

    <Important>

        - ONLY USE THE INFORMATION BEING PROVIDED TO YOU.
        - Return this output as a JSON OBJECT in <Output></Output> XML tags. The format would be the following: 
        <Output>
            {{
                "minimum_average": calculated_value, # Lowest integer
                "average": calculated_value,    # Mid value integer
                "maximum_average": calculated_value, # Highest integer
                "currency" : 'currency of values' # USD, INR, etc
            }}
        </Output>

        values should be integers, not strings, without commas (e.g., 100000, not 100,000).
        You must follow this format strictly.
        minimum average would be the lowest average, average will be above it and maximum average will be the highest average. Ensure these values are written as integers.
    
    </Important>
    
    Information: {information}

    """

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]

    output = await invoke(
        messages=messages,
        model="openai/gpt-4o-mini",
        temperature=0,
        fallbacks=["anthropic/claude-3-5-haiku-latest"],
    )

    start_idx = output.rfind("<Output>") + 8
    end_idx = output.rfind("</Output>")
    salary = output[start_idx:end_idx]

    return eval(salary.strip())


async def safe_call(func, *args, timeout=45):
    try:
        return await asyncio.wait_for(func(*args), timeout)
    except asyncio.TimeoutError:
        return None


async def actual_salaries(ids, background_task, client, db_client):
    tasks = [
        all_title_salary_final(id, background_task, client, db_client) for id in ids
    ]
    results = await asyncio.gather(*tasks)
    currencies_task = []
    all_salaries = []

    for result in results:
        if not result:
            continue
        try:
            max_value = (
                max(map(int, list(result.keys())))
                if len(list(result.keys())) > 0
                else ""
            )
            salary = result[str(max_value)]["baseSalary"]

            splits = salary.strip().split(" ")
            currency = splits[0]
            salary = int(splits[1].replace(",", ""))

            all_salaries.append(salary)
            currencies_task.append(search_cik(currency))
        except Exception as e:
            print(e)
            continue

    if len(currencies_task) < 3:
        return {}

    all_rates = await asyncio.gather(*currencies_task)

    for index, rate in enumerate(all_rates):
        all_salaries[index] = all_salaries[index] * rate

    if len(all_salaries) < 3:
        return {}
    average = round(np.percentile(all_salaries, 50))
    percentile_25 = round(np.percentile(all_salaries, 25))
    percentile_75 = round(np.percentile(all_salaries, 75))

    sorted_numbers = sorted([average, percentile_25, percentile_75], reverse=True)
    p75, p50, p25 = sorted_numbers

    final_answer = {
        "p25": p25,
        "p75": p75,
        "averagePay": p50,
        "medianPay": p50,
    }
    return final_answer


async def glassdoor(titles):

    if len(titles) > 0:
        glassdoor_tasks = []
        titles = titles
        for title in titles:
            glassdoor_tasks.append(get_glassdoor_salary(title[0], title[1]))

        subtasks = [
            glassdoor_tasks[i : i + 10] for i in range(0, len(glassdoor_tasks), 10)
        ]
        results = []
        for j in subtasks:
            temp_results = await asyncio.gather(*j)
            results = results + temp_results

        subtasks = []
        total_not_None = []
        for item in results:
            if item and "currency" in item:
                subtasks.append(search_cik(item["currency"]))
                total_not_None.append(item)

        exchange_rates = await asyncio.gather(*subtasks)
        results = []

        total_maximum_average = 0
        total_minimum_average = 0
        total_average = 0
        total_average_list = []
        for index, item in enumerate(total_not_None):
            if item["closest_25"] and item["closest_75"] and item["closest_50"]:
                total_minimum_average += item["closest_25"] * exchange_rates[index]
                total_maximum_average += item["closest_75"] * exchange_rates[index]
                total_average += item["closest_50"] * exchange_rates[index]
                total_average_list.append(item["closest_50"] * exchange_rates[index])

        total_minimum_average = round(total_minimum_average / len(exchange_rates))
        total_maximum_average = round(total_maximum_average / len(exchange_rates))
        average = round(total_average / len(exchange_rates))

        try:
            if len(total_average_list) > 5:
                percentile_50 = round(np.percentile(total_average_list, 50))
                percentile_25 = round(np.percentile(total_average_list, 25))
                percentile_75 = round(np.percentile(total_average_list, 75))

                values = {percentile_50, percentile_25, percentile_75}
                if len(values) == 3:
                    final_answer = {
                        "p25": percentile_25,
                        "p75": percentile_75,
                        "averagePay": percentile_50,
                        "medianPay": percentile_50,
                    }

                    return final_answer
        except:
            pass

        sorted_numbers = sorted(
            [total_minimum_average, total_maximum_average, average], reverse=True
        )
        p75, p50, p25 = sorted_numbers

        final_answer = {
            "p25": p25,
            "p75": p75,
            "averagePay": p50,
            "medianPay": p50,
        }

        return final_answer


async def Calculations(filters_data, client, background_task, db_client):

    cached_data = await fetch_value_by_key(filters_data["profileIds"])
    if cached_data:
        return cached_data

    if "assignment" not in filters_data:

        data = {
            "industry": filters_data["industry"],
            "job_titles": filters_data["job_titles"] + filters_data["management_level"],
            "location": filters_data["location"],
            "experience": filters_data["experience"],
            "ids": filters_data["profileIds"],
            "companies": filters_data["company"],
        }

        flag = False
        if len(data["location"]) == 0:
            data["location"] = ["United States"]
            flag = True

    else:
        data = {
            "industry": [],
            "job_titles": [],
            "location": [],
            "experience": [],
            "ids": [],
            "companies": [],
        }
        flag = True

    prompts = []
    tasks = []
    companies = data["companies"]

    for job_title, location, company in product(
        data["job_titles"], data["location"], companies
    ):
        prompt = f"Average pay of {job_title} in company {company}, in {location}"

        prompts.append(prompt)

    for job_title, location in product(data["job_titles"], data["location"]):
        prompt = f"Average pay for {job_title} in {location}"

        prompts.append(prompt)

    if len(prompts) == 0 and len(companies) != 0:
        for company, location in product(companies, data["location"]):
            prompt = f"Average pay in the company {company}, in {location}"

            prompts.append(prompt)

    if len(prompts) == 0:
        for industry, location in product(data["industry"], data["location"]):
            prompt = f"Average pay in {industry} industry in {location}"

            prompts.append(prompt)

    if len(prompts) == 0:
        for experience, location in product([data["experience"]], data["location"]):
            if len(experience) != 0:
                minn = experience[0]
                maxx = experience[1]
                prompt = (
                    f"Average pay with {minn}-{maxx} years of experience in {location}"
                )

                prompts.append(prompt)

    titles = []
    if len(filters_data["profileIds"]) != 0:

        if len(filters_data["profileIds"]) > 100:
            random_elements = random.sample(filters_data["profileIds"], 100)
        else:
            random_elements = filters_data["profileIds"]

        query = {
            "_source": [
                "headline",
                "experience.title",
                "experience.end",
                "country",
            ],
            "query": {
                "bool": {
                    "must": [
                        {"terms": {"_id": random_elements}},
                        {
                            "nested": {
                                "path": "experience",
                                "query": {
                                    "bool": {
                                        "must_not": {
                                            "exists": {"field": "experience.end"}
                                        }
                                    }
                                },
                            }
                        },
                    ]
                }
            },
        }

        search_response = await client.search(
            index=os.getenv("ES_PROFILES_INDEX"), body=query
        )
        for data in search_response["hits"]["hits"]:

            location = data["_source"]["country"] if data["_source"]["country"] else ""
            experience = (
                data["_source"]["experience"] if "experience" in data["_source"] else []
            )

            for item in experience:
                if not item["end"]:
                    title = item["title"]
                    prompt = f"Average pay for {title} in United States"

                    titles.append([title, location])
                    prompts.append(prompt)
                    break

    if len(titles) > 0:
        try:
            final_answer = await glassdoor(titles)
            await insert_into_cache_talent_map_salary(
                filters_data["profileIds"], final_answer
            )
            return final_answer
        except Exception as e:
            print("Problem: ", e)
            pass

    if len(prompts) == 0:
        for location in data["location"]:
            tasks.append(proxy_inference(f"Average pay in {location}"))
            prompts.append(f"Average pay for in {location}")

    tasks = []
    for i in prompts:
        tasks.append(proxy_inference(i))

    if len(tasks) < 101:
        results = await asyncio.gather(*tasks)
    else:
        subtasks = [tasks[i : i + 300] for i in range(0, len(tasks), 300)]
        tasks = []
        results = []
        for j in subtasks:
            temp_results = await asyncio.gather(*j)
            results = results + temp_results

    new_tasks = []
    for index, answer in enumerate(results):
        temp_payload = ""
        for entry in answer["query_result"]:
            title = entry.get("title")
            snippet = entry.get("snippet")
            link = entry.get("link")
            if "search.yahoo.com" in link:
                try:
                    link = unquote(link.split("/RU=")[1].split("/RK=")[0])
                except:
                    pass
            extracted_info = tldextract.extract(link)
            site = extracted_info.domain.title()

            temp_payload += f"""The following is a snippet of an article from '{site}' titled '{title}'

                                "{snippet}"


                            """
        new_tasks.append(average_pay_snippets(prompts[index], temp_payload))

    salaries = await asyncio.gather(*new_tasks)

    currency_tasks = []
    for dictionary in salaries:
        currency_tasks.append(search_cik(dictionary["currency"]))

    exchange_rates = await asyncio.gather(*currency_tasks)
    total_maximum_average = 0
    total_minimum_average = 0
    total_average = 0
    total_average_list = []
    for index, exchange_rate in enumerate(exchange_rates):
        total_maximum_average += round(
            salaries[index]["maximum_average"] * exchange_rate
        )
        total_minimum_average += round(
            salaries[index]["minimum_average"] * exchange_rate
        )
        total_average += round(salaries[index]["average"] * exchange_rate)

        total_average_list.append(round(salaries[index]["average"] * exchange_rate))

    total_minimum_average = round(total_minimum_average / len(exchange_rates))
    total_maximum_average = round(total_maximum_average / len(exchange_rates))
    average = round(total_average / len(exchange_rates))

    try:
        if len(total_average_list) > 2:
            percentile_50 = round(np.percentile(total_average_list, 50))
            percentile_25 = round(np.percentile(total_average_list, 25))
            percentile_75 = round(np.percentile(total_average_list, 75))

            final_answer = {
                "p25": percentile_25,
                "p75": percentile_75,
                "averagePay": percentile_50,
                "medianPay": percentile_50,
            }
            await insert_into_cache_talent_map_salary(
                filters_data["profileIds"], final_answer
            )

            return final_answer
    except:
        pass

    sorted_numbers = sorted(
        [total_minimum_average, total_maximum_average, average], reverse=True
    )
    p75, p50, p25 = sorted_numbers

    final_answer = {
        "p25": p25,
        "p75": p75,
        "averagePay": p50,
        "medianPay": p50,
    }

    await insert_into_cache_talent_map_salary(filters_data["profileIds"], final_answer)

    return final_answer
