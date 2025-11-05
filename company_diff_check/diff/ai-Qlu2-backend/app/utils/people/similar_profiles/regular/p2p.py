import re
import asyncio
from bs4 import BeautifulSoup
import urllib.request as urllib2

from app.utils.people.similar_profiles.regular.linkedin_identifier import (
    get_linkedin_identifier,
)
from qutils.database.post_gres import postgres_fetch_all
from qutils.llm.asynchronous import invoke


async def get_company_data(universal_names, client):
    body = {
        "_source": [
            "li_name",
            "li_size",
            "li_industries",
            "li_specialties",
            "li_universalname",
            "li_description",
        ],
        "query": {"terms": {"li_universalname": universal_names}},
    }
    data = await client.search(index="company", body=body)
    response = {}
    for i in data["hits"]["hits"]:
        company_string = ""
        source = i.get("_source", "")
        if source:
            li_size = source.get("li_size", 0)
            li_name = source.get("li_name", "")
            li_specialties = source.get("li_specialties", "")
            li_industry = source.get("li_industries", "")
            if not isinstance(li_specialties, list):
                li_specialties = [li_specialties]
            li_description = source.get("li_description", "")
            if not li_size:
                li_size = 0
            if li_size >= 3000:
                company_string += f"<comapny> {li_name} </company>"
            else:
                company_string += f"<company>\n<industries> {li_industry + li_specialties} </industry>\n<description> {li_description} </description>\n</company>"
        response[source.get("li_universalname")] = {
            "string": company_string,
            "name": li_name,
        }
    return response


async def get_company_data_base(universal_names, client):
    body = {
        "_source": [
            "li_name",
            "li_size",
            "li_industries",
            "li_specialties",
            "li_universalname",
            "li_description",
        ],
        "query": {"terms": {"li_universalname": universal_names}},
    }
    data = await client.search(index="company", body=body)
    return data


def post_process_gpt_output(response):
    return (
        response[response[: response.rfind("<")].rfind("<") :]
        .split("<")[1]
        .split(">")[1]
        .strip()
    )


async def filter_similar_companies_p2p(
    ground_truth, company_name, company_data, li_universalname, v2=False
):
    if v2:
        system_prompt = """<role> You are Jerry, an expert in finding similar profiles for recruiters </role>
<instructions>
- A good similar profiles needs to focus on company similarity and the person's role
- Given a target profile and some company information, answer the chances of finding a similar profile from the provided company
- Answer the user query by first outputting your reasoning in 3 lines then assign a score between 1-4 in <score> </score> tags
- Score of 1 means upto 25% chance, score of 2 means upto 50% chance, score of 3 means upto 75% chance and a score of 4 means upto 100% chance
</instructions>"""

        user_prompt = (
            ground_truth + f"<target_company> {company_data} </target_company>"
        )
    else:
        system_prompt = f"""<role> You are an expert in finding good candidates for a specific job role </role>
<instructions>
- How likely is it that {company_name} is involved in "{ground_truth}" 
- Output your thought process in 3 lines before final score as 1, 2, 3 or 4 in <score> </score> tags
- score of 1 means highly unlikely and the target field is irrelevant to the industry of company, score of 2 means less than 50% match, score of 3 means more than 50% match, score of 4 means perfect match
</instructions>"""

        user_prompt = company_data

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    response = await invoke(
        messages=messages,
        temperature=0,
        model="openai/gpt-4o-mini",
        fallbacks=["anthropic/claude-3-5-haiku-latest"],
    )

    matches = re.findall(r"<score>(.*?)</score>", response)
    if matches:
        return li_universalname, int(matches[0].strip())

    return li_universalname, 1


async def verification(mapping, ground_truth, profile_string):

    filtering_tasks = []
    if profile_string:
        for universalname in mapping:
            filtering_tasks.append(
                filter_similar_companies_p2p(
                    profile_string,
                    mapping[universalname].get("name"),
                    mapping[universalname].get("string"),
                    universalname,
                    True,
                )
            )
    else:
        for universalname in mapping:
            filtering_tasks.append(
                filter_similar_companies_p2p(
                    ground_truth,
                    mapping[universalname].get("name"),
                    mapping[universalname].get("string"),
                    universalname,
                )
            )
    res = await asyncio.gather(*filtering_tasks)
    final = [item[0] for item in res if item[1] > 2]
    return final


async def company_recommender(company_name: str, ground_truth, client, profile_string):
    try:
        base_universal_name = await get_linkedin_identifier(
            company_name, None, client, None
        )
    except:
        return []

    if not base_universal_name:
        return []

    select_query = f"select * from linked_in_staging_data where universal_name = '{base_universal_name}'"
    try:
        res = await postgres_fetch_all(select_query)
        li_universalnames = []

        if res and len(res) > 0 and len(res[0]) > 1 and isinstance(res[0][1], dict):
            similar_pages = res[0][1].get("similar_pages", [])
            if similar_pages and isinstance(similar_pages, list):
                universal_names = []
                for i in similar_pages:
                    if "company/" in i and "?trk=" in i:
                        universalname = i[
                            i.find("company/") + len("company/") : i.find("?trk=")
                        ]
                        if universalname:
                            universal_names.append(universalname)
                li_universalnames = universal_names
            else:
                pass
        else:
            user_agent = (
                "Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_6_4; en-US) "
                "AppleWebKit/534.3 (KHTML, like Gecko) Chrome/6.0.472.63 Safari/534.3"
            )
            headers = {"User-Agent": user_agent}

            try:
                req = urllib2.Request(
                    f"https://www.linkedin.com/company/{base_universal_name}",
                    None,
                    headers,
                )
                response = urllib2.urlopen(req)
                page = response.read()
                response.close()

                soup = BeautifulSoup(page, "html.parser")
                a_tags = soup.findAll("a", href=True)

                for a_tag in a_tags:
                    href_val = a_tag["href"]
                    if "?trk=similar-pages" in href_val and "company/" in href_val:
                        start_idx = href_val.find("company/") + len("company/")
                        end_idx = href_val.find("?trk=")
                        universalname = href_val[start_idx:end_idx]
                        if universalname:
                            li_universalnames.append(universalname)
            except:
                pass

        p2p_companies = []
        if li_universalnames:
            mapping = {}
            try:
                mapping = await get_company_data(li_universalnames, client)
            except:
                pass

            try:
                p2p_companies = await verification(
                    mapping, ground_truth, profile_string
                )
            except Exception as e:
                p2p_companies = []
        else:
            p2p_companies = []

        p2p_companies.append(base_universal_name)
        return p2p_companies

    except Exception as e:
        return []
