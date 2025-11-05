import os
import asyncio
import logging

from qutils.llm.asynchronous import invoke

from app.utils.search.aisearch.product.summary.utils import post_process_gpt_output
from app.utils.search.aisearch.product.summary.prompts import (
    SUMMARY_GENERATING_SYSTEM_PROMPT,
    SUMMARY_GENERATING_USER_PROMPT,
)
from app.core.database import postgres_fetch, postgres_insert

logger = logging.getLogger(__name__)


async def insert_summary(
    product_identifier, product_name, company_identifier, company_name, summary
):
    try:
        if product_identifier and company_identifier:
            safe_company_name = company_name.replace("'", "''")
            safe_product_name = product_name.replace("'", "''")
            safe_summary = summary.replace("'", "''")
            tuples = [
                f"('{company_identifier}', '{safe_company_name}', '{safe_product_name.lower().strip()}', '{product_identifier}', '{safe_summary}')"
            ]
            values_clause = ", ".join(tuples)
            query = f"""
                INSERT INTO company_products_summary (li_universalname, li_name, product_name, product_identifier, summary)
                VALUES {values_clause}
                ON CONFLICT (product_identifier) DO NOTHING;
            """
            await postgres_insert(query)
    except:
        return


async def fetch_summary(product_identifier):
    try:
        query = f"""
            SELECT (product_identifier, product_name, li_universalname, li_name, summary) from company_products_summary
            WHERE product_identifier = '{product_identifier}'
        """
        identifier = await postgres_fetch(query)
        if identifier:
            return identifier[0]
    except:
        return None


async def get_industry_description(company_identifier, client):

    try:
        result = await client.search(
            body={
                "size": 1,
                "_source": [
                    "li_name",
                    "li_description",
                    "li_subindustries",
                    "li_industries",
                ],
                "query": {"term": {"li_universalname": {"value": company_identifier}}},
            },
            index=os.getenv("ES_COMPANIES_INDEX"),
        )
        es_result = result["hits"]["hits"][0]
        name = es_result["_source"].get("li_name", "")
        li_description = es_result["_source"].get("li_description", "")
        li_industries = es_result["_source"].get("li_industries", [])
        li_subindustries = es_result["_source"].get("li_subindustries", [])
        if isinstance(li_industries, list) and len(li_industries):
            li_industries = li_industries[0]
        es_result = es_result["_id"]
        if li_description or li_industries:
            return {
                "name": name,
                "Description": li_description,
                "Industries": li_industries,
                "Sub Industries": li_subindustries,
            }
        return None
    except:
        return None


async def generate_summary(
    product_identifier, product_name, company_identifier, company_name, client
):
    summary = await fetch_summary(product_identifier)
    if summary:
        return {"summary": summary[4]}

    data = await get_industry_description(company_identifier, client)
    user_prompt = (
        SUMMARY_GENERATING_USER_PROMPT
        + f"""
            <Product Name>
                {product_name}
            </Product Name>
            <Company Name>
                {company_name}
            </Company Name>
            <Company Details>
                {data}
            </Company Details>
        """
    )
    response = await invoke(
        messages=[
            {"role": "system", "content": SUMMARY_GENERATING_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        model="groq/openai/gpt-oss-120b",
        fallbacks=["openai/gpt-4.1"],
    )
    logger.info(f"LLM Response for product summary of {product_name}: {response}")
    summary = post_process_gpt_output(response)
    if summary == "None":
        return None
    else:
        asyncio.create_task(
            insert_summary(
                product_identifier,
                product_name,
                company_identifier,
                company_name,
                summary,
            )
        )
        return {"summary": summary}
