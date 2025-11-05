import ulid
import json
import asyncio
from app.core.database import (
    postgres_fetch,
    postgres_insert,
    postgres_fetch_all,
    postgres_insert_tuples,
)

from app.utils.search.aisearch.product.generation.utils import post_process_gpt_output
from app.utils.search.aisearch.product.generation.prompts import (
    PRODUCT_COMPETITOR_SYSTEM_PROMPT,
    PRODUCT_COMPETITOR_USER_PROMPT,
    ALL_PRODUCT_GENERATION_USER_PROMPT,
    ALL_PRODUCT_GENERATION_SYSTEM_PROMPT,
    CLAUDE_PROD_CHECK_USER,
    CLAUDE_PROD_CHECK_SYSTEM,
    COMPANY_CHECKING_USER_PROMPT,
    COMPANY_CHECKING_SYSTEM_PROMPT,
    PRODUCT_GENERATION_USER_PROMPT,
    PRODUCT_GENERATION_SYSTEM_PROMPT,
)
from app.utils.search.aisearch.company.generation.mapping import map_company
from app.utils.search.aisearch.company.generation.elastic import get_company_source
from app.utils.search.aisearch.product.generation.logo import (
    get_product_image,
    process_images,
)
from app.utils.search.aisearch.product.summary.main import get_industry_description
from app.utils.search.aisearch.company.generation.main import generate

from qutils.llm.asynchronous import invoke


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
        messages=[
            {
                "role": "system",
                "content": "You are a relevant industry name generating agent.",
            },
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        model="groq/llama-3.3-70b-versatile",
        fallbacks=["openai/gpt-4.1"],
    )

    return post_process_gpt_output(response)


async def prod_checking_agent(user_query, prompt):
    user_prompt = (
        CLAUDE_PROD_CHECK_USER
        + f"""
            <Input>
                User Query: {user_query}
                Company Prompt: {prompt}
            </Input>
        """
    )
    response = await invoke(
        messages=[
            {"role": "system", "content": CLAUDE_PROD_CHECK_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        model="anthropic/claude-sonnet-4-latest",
        fallbacks=["openai/gpt-4.1"],
    )
    try:
        industry = response.split("<Prediction>")[1].split("</Prediction>")[0].strip()
        if industry.lower() == "no" or industry == "":
            return None
        return {"product_prompt": industry}
    except:
        return None


async def company_industry_existence(prompt):
    user_prompt = (
        COMPANY_CHECKING_USER_PROMPT
        + f"""
            <User-Prompt>
                {prompt}
            </User-Prompt>
        """
    )
    response = await invoke(
        messages=[
            {"role": "system", "content": COMPANY_CHECKING_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        model="openai/gpt-4.1",
        fallbacks=["anthropic/claude-sonnet-4-latest"],
    )
    industry = response.split("<industry>")[1].split("</industry>")[0].strip()
    company = response.split("<company>")[1].split("</company>")[0].strip()
    company = [element.strip() for element in company.split("|||")]
    if company == [""]:
        company = None
    if industry == "":
        industry = None
    return company, industry


async def insert_product(
    li_name, li_universalname, product_name, product_identifier, logo
):
    try:
        if product_identifier and li_universalname and len(product_name) < 50:
            safe_li_name = li_name.replace("'", "''")
            safe_product_name = product_name.strip().replace("'", "''")
            tuples = [
                f"('{li_universalname}', '{safe_li_name}', '{safe_product_name.strip()}', '{product_identifier}' , '{logo}', false)"
            ]
            values_clause = ", ".join(tuples)
            query = f"""
                INSERT INTO company_products (li_universalname, li_name, product_name, product_identifier, logo, flag)
                VALUES {values_clause}
                ON CONFLICT (product_name, li_name)
                DO UPDATE SET flag = false
                WHERE company_products.product_name = '{safe_product_name.strip()}'
                AND company_products.li_name = '{safe_li_name}';
            """
            await postgres_insert(query)
    except Exception as e:
        print(e)
        return None


async def insert_all_products_with_logos(products):
    try:
        valid_products = [
            product
            for product in products
            if product.get("product_identifier")
            and product.get("li_universalname")
            and product.get("logo")
            and len(product.get("product_name")) < 50
        ]
        if not valid_products:
            return None
        product_query = """
            INSERT INTO company_products (li_universalname, li_name, product_name, product_identifier, logo)
            VALUES (
                :li_universalname, 
                :li_name, 
                :product_name,
                :product_identifier,
                :logo
            )
            ON CONFLICT (product_name, li_name)
            DO UPDATE SET flag = false
            WHERE company_products.product_name = :product_name
            AND company_products.li_name = :li_name;
        """

        await postgres_insert_tuples(product_query, valid_products)
        return True
    except Exception as e:
        print("ERROR IN BULK PRODUCT AND LOGO INSERTION: ", e)
        return None


async def fetch_product(product_name, li_name):
    try:
        product_name = product_name.strip()
        safe_product_name = product_name.replace("'", "''")
        safe_li_name = li_name.replace("'", "''")

        query = f"""
            SELECT li_universalname, li_name, product_name, product_identifier
            FROM company_products
            WHERE product_name = '{safe_product_name}'
            AND li_name = '{safe_li_name}'
            AND flag = false
        """
        identifier = await postgres_fetch(query)
        return identifier
    except:
        return None


async def get_gpt_all_products_for_company(company_name):
    user_prompt = (
        ALL_PRODUCT_GENERATION_USER_PROMPT
        + f"""
            <Company Name>
                {company_name}
            </Company Name>
        """
    )
    response = await invoke(
        messages=[
            {"role": "system", "content": ALL_PRODUCT_GENERATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        model="openai/gpt-4.1",
        fallbacks=["anthropic/claude-sonnet-4-latest"],
    )
    response = post_process_gpt_output(response)
    products = [element.strip() for element in response.split("|||")]
    if products == [""]:
        return None
    else:
        return products


async def get_gpt_products_for_company(
    prompt, company_name, user_query=None, db_products=None
):
    user_prompt = (
        PRODUCT_GENERATION_USER_PROMPT
        + f"""
            <User-Prompt>
                {prompt}
            </User-Prompt>
            <User-Query>
                {user_query}
            </User-Query>
            <Company Name>
                {company_name}
            </Company Name>
            <Existing Products>
                {db_products}
            </Existing Products>
        """
    )
    response = await invoke(
        messages=[
            {"role": "system", "content": PRODUCT_GENERATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.05,
        model="openai/gpt-4.1",
        fallbacks=["anthropic/claude-sonnet-4-latest"],
    )
    try:
        pureplay = response.split("<pureplay>")[1].split("</pureplay>")[0].strip()
        response = response.split("<Products>")[1].split("</Products>")[0].strip()
        if response:
            product = [element.strip() for element in response.split("|||")]
            if product == [""]:
                return None, None, None
            else:
                products = [element.split("~")[0].strip() for element in product]
                category = [element.split("~")[1].strip() for element in product]
                return products, category, pureplay
        return None, None, None
    except:
        return None, None, None


async def get_company_products_tab(li_universalname, li_name, es_id):
    try:
        safe_li_universalname = li_universalname.replace("'", "''")

        query = f"""
                SELECT li_universalname, li_name, product_identifier, product_name 
                FROM company_products
                WHERE li_universalname = '{safe_li_universalname}'
                AND flag = false
            """
        identifier = await postgres_fetch_all(query)

        if len(identifier) > 0:
            formatted_products = [
                {
                    "es_id": es_id,
                    "li_universalname": row[0],
                    "li_name": row[1],
                    "product_identifier": row[2],
                    "product_name": row[3],
                }
                for row in identifier
            ]
            return formatted_products
        else:
            products = await get_gpt_all_products_for_company(li_name)
            product_processing_tasks = [
                process_parallel_products_for_all(
                    product, li_name, li_universalname, es_id
                )
                for product in products
            ]
            output = await asyncio.gather(*product_processing_tasks)
            valid_products = [item for item in output if item is not None]
            ingest = await insert_all_products_with_logos(valid_products)
            if ingest:
                formatted_products = [
                    {
                        key: value
                        for key, value in json_obj.items()
                        if key not in {"logo"}
                    }
                    for json_obj in valid_products
                ]
                return formatted_products
    except:
        return None


async def get_company_products(li_universalname, es_id):
    try:
        safe_li_universalname = li_universalname.replace("'", "''")

        query = f"""
                SELECT li_universalname, li_name, product_identifier, product_name 
                FROM company_products
                WHERE li_universalname = '{safe_li_universalname}'
                AND flag = false
            """
        identifier = await postgres_fetch_all(query)

        if len(identifier) > 0:
            formatted_products = [
                {
                    "es_id": es_id,
                    "li_universalname": row[0],
                    "li_name": row[1],
                    "product_identifier": row[2],
                    "product_name": row[3],
                }
                for row in identifier
            ]
            return formatted_products
        else:
            return None
    except:
        return None


async def get_product_data(product_identifier):
    try:
        query = f"""
            SELECT li_universalname, li_name, product_identifier, product_name 
            FROM company_products
            WHERE product_identifier = '{product_identifier}'
        """
        identifier = await postgres_fetch(query)
        if len(identifier) > 3:
            return {
                "li_universalname": identifier[0],
                "li_name": identifier[1],
                "product_identifier": identifier[2],
                "product_name": identifier[3],
            }
        return None
    except Exception as e:
        print(f"Error fetching product data: {e}")
        return None


async def product_logos(li_name, product_name, product_identifier):
    try:
        if len(product_name) < 50:
            image = await get_product_image(li_name, product_name)
            if image:
                logo = await process_images(
                    product_identifier, [image], icon_size=(128, 128)
                )
                logo = logo[0]
                if logo:
                    return logo
            return None
        return None
    except:
        return None


async def process_parallel_products(
    product,
    li_name,
    li_universalname,
    es_id,
    category=None,
    urn=None,
    industry=None,
    pureplay=None,
):
    try:
        payload = None
        identifier = await fetch_product(product, li_name)
        if identifier:
            identifier = identifier[3]
            payload = {
                "es_id": es_id,
                "li_universalname": li_universalname,
                "li_name": li_name,
                "product_identifier": identifier,
                "product_name": product,
            }
            if category:
                payload["key_term"] = [category]
            if pureplay:
                payload["pureplay"] = pureplay
            if urn:
                payload["li_urn"] = urn
            if industry:
                payload["li_industries"] = industry
        else:
            identifier = str(ulid.new())
            logo = await product_logos(li_name, product, identifier)
            if logo:
                payload = {
                    "es_id": es_id,
                    "li_universalname": li_universalname,
                    "li_name": li_name,
                    "product_identifier": identifier,
                    "product_name": product,
                }
                if category:
                    payload["key_term"] = [category]
                if pureplay:
                    payload["pureplay"] = pureplay
                if urn:
                    payload["li_urn"] = urn
                if industry:
                    payload["li_industries"] = industry
                asyncio.create_task(
                    insert_product(li_name, li_universalname, product, identifier, logo)
                )
        return payload
    except Exception as e:
        print(
            f"Error in processing parallel products of the company: {li_name}, Error: {e}"
        )
        return None


async def process_parallel_products_for_all(product, li_name, li_universalname, es_id):
    try:
        identifier = str(ulid.new())
        logo = await product_logos(li_name, product, identifier)
        if logo:
            payload = {
                "es_id": es_id,
                "li_universalname": li_universalname,
                "li_name": li_name,
                "product_identifier": identifier,
                "product_name": product,
                "logo": logo,
            }
            return payload
    except Exception as e:
        print("Error in processing in parallel for all: ", e)
    return None


async def ingest_all_products(li_name, li_universalname, es_id):
    try:
        products = await get_gpt_all_products_for_company(li_name)
        if not products:
            return None
        product_processing_tasks = [
            process_parallel_products_for_all(product, li_name, li_universalname, es_id)
            for product in products
        ]
        output = await asyncio.gather(*product_processing_tasks)
        valid_products = [item for item in output if item is not None]
        if valid_products:
            ingest = await insert_all_products_with_logos(valid_products)
            if ingest:
                filtered_list = [
                    {
                        key: value
                        for key, value in json_obj.items()
                        if key not in {"logo", "es_id"}
                    }
                    for json_obj in valid_products
                ]
                return filtered_list
        return None
    except:
        return None


async def generate_products(
    user_query, prompt, li_name, li_universalname, es_id, li_urn, li_industries
):
    # ALWAYS get db_products first
    db_products = await get_company_products(li_universalname, es_id)
    if not db_products:
        db_products = await ingest_all_products(li_name, li_universalname, es_id)

    # ALWAYS call get_gpt_products_for_company with db_products
    gpt_products, gpt_category, pureplay = await get_gpt_products_for_company(
        prompt, li_name, user_query, db_products
    )

    if gpt_products is None or not gpt_products or not gpt_category:
        return None
    else:
        if len(gpt_products) > 3 and len(gpt_products) < 6:
            gpt_products = gpt_products[:3]
            gpt_category = gpt_category[:3]

        if gpt_products:
            product_processing_tasks = [
                process_parallel_products(
                    product,
                    li_name,
                    li_universalname,
                    es_id,
                    category,
                    li_urn,
                    li_industries,
                    pureplay,
                )
                for product, category in zip(gpt_products, gpt_category)
            ]

            output = await asyncio.gather(*product_processing_tasks)
            return [item for item in output if item is not None]
        return None


async def get_all_products(user_query, prompt, companies):
    tasks = []
    for company in companies:
        li_name = company.li_name
        li_universalname = company.li_universalname
        es_id = company.es_id
        li_urn = company.li_urn
        li_industries = company.li_industries
        tasks.append(
            asyncio.create_task(
                generate_products(
                    user_query,
                    prompt,
                    li_name,
                    li_universalname,
                    es_id,
                    li_urn,
                    li_industries,
                )
            )
        )
    products = await asyncio.gather(*tasks)

    output = [item for product in products if product is not None for item in product]
    return output if output else None


async def process_es_source(
    gpt_products, gpt_category, es_data, es_id, prompt, pureplay
):
    try:
        li_name = es_data["li_name"]
        li_universalname = es_data["li_universalname"]
        urn = es_data["li_urn"]
        industry = es_data["li_industries"]
        if isinstance(industry, list):
            industry = str(industry[0]) if industry else ""
        elif isinstance(industry, str):
            industry = industry
        output = []

        # No need to fetch db_products again - gpt_products already considers them
        # The caller already fetched db_products and called get_gpt_products_for_company
        if gpt_products:
            product_processing_tasks = [
                process_parallel_products(
                    product,
                    li_name,
                    li_universalname,
                    es_id,
                    category,
                    urn,
                    industry,
                    pureplay,
                )
                for product, category in zip(gpt_products, gpt_category)
            ]
            product_results = await asyncio.gather(*product_processing_tasks)
            output.extend([result for result in product_results if result is not None])
            return output
        return None

    except (IndexError, KeyError, TypeError) as e:
        print(f"Error processing product for company: {e}")
        return None


async def process_single_company(prompt, es_source, es_id):
    """Process a single company and return the results as a list."""
    try:
        # Get existing products from database first
        li_name = es_source["li_name"]
        li_universalname = es_source["li_universalname"]
        db_products = await get_company_products(li_universalname, es_id)
        if not db_products:
            db_products = await ingest_all_products(li_name, li_universalname, es_id)

        gpt_products, gpt_category, pureplay = await get_gpt_products_for_company(
            prompt, li_name, None, db_products
        )

        if not gpt_products:
            return None
        if len(gpt_products) > 3 and len(gpt_products) < 6:
            gpt_products = gpt_products[:3]
            gpt_category = gpt_category[:3]

        es_source_result = await process_es_source(
            gpt_products, gpt_category, es_source, es_id, prompt, pureplay
        )

        return es_source_result

    except Exception as company_error:
        print("Error in processing a company: ", company_error)
        return None


async def generate_products_stream(prompt, client, mysql_pool, redis_client):
    results_queue = asyncio.Queue()

    async def producer_and_worker_manager():
        processing_tasks = set()

        async def process_and_queue_company(es_source, es_id):
            try:
                products = await process_single_company(prompt, es_source, es_id)
                if products:
                    await results_queue.put(products)
            except Exception as e:
                print(f"Error processing company {es_id}: {e}")

        async for result in generate(
            current_prompt=prompt,
            past_prompt="",
            userquery=prompt,
            es_client=client,
            mysql_pool=mysql_pool,
            redis_client=redis_client,
            product_filter=True,
        ):
            if "data: {" not in result:
                continue

            data = json.loads(result[result.find("{") : result.rfind("}") + 1])
            es_id = data.get("es_data", {}).get("es_id")
            es_source = data.get("es_source")

            if not es_id or not es_source:
                continue

            task = asyncio.create_task(process_and_queue_company(es_source, es_id))
            processing_tasks.add(task)
            task.add_done_callback(processing_tasks.discard)

        if processing_tasks:
            await asyncio.wait(processing_tasks)

        await results_queue.put(None)

    manager_task = asyncio.create_task(producer_and_worker_manager())

    while True:
        products = await results_queue.get()
        if products is None:
            break

        for product_data in products:
            yield f"data: {json.dumps(product_data, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)

    await manager_task


async def insert_competitors(
    product_identifier, product_name, company_identifier, company_name, competitors
):
    try:
        if product_identifier and company_identifier and competitors:
            safe_company_name = company_name.replace("'", "''")
            safe_product_name = product_name.strip().replace("'", "''")
            tuples = [
                f"('{company_identifier}', '{safe_company_name}', '{safe_product_name}', '{product_identifier}', '{json.dumps(competitors)}')"
            ]
            values_clause = ", ".join(tuples)
            query = f"""
                INSERT INTO company_products_competitor (li_universalname, li_name, product_name, product_identifier, competitors)
                VALUES {values_clause}
                ON CONFLICT (product_identifier) DO NOTHING;
            """
            await postgres_insert(query)
    except:
        return


async def fetch_competitors(product_identifier):
    try:
        query = f"""
            SELECT product_identifier, product_name, li_universalname, li_name, competitors
            FROM company_products_competitor
            WHERE product_identifier = '{product_identifier}'
        """
        identifier = await postgres_fetch(query)
        if identifier:
            return identifier
    except:
        return None


async def process_competitors(products, es_id, es_data, product_name, company_name):
    li_name = es_data["li_name"]
    li_universalname = es_data["li_universalname"]

    db_products = await get_company_products(li_universalname, es_id)
    if not db_products:
        db_products = await ingest_all_products(li_name, li_universalname, es_id)

    if db_products and products:
        if isinstance(products, str):
            products = [products]

        product_processing_tasks = [
            process_parallel_products(product, li_name, li_universalname, es_id)
            for product in products
        ]
        competitors = await asyncio.gather(*product_processing_tasks)
        return competitors
    return None


async def get_product_competitors(
    product_name,
    product_identifier,
    company_name,
    company_identifier,
    client,
    mysql_pool,
    redis_client,
):
    competitors = await fetch_competitors(product_identifier)
    if competitors:
        return competitors[4]

    data = await get_industry_description(company_identifier, client)
    user_prompt = (
        PRODUCT_COMPETITOR_USER_PROMPT
        + f"""
            <Company Name>
                {company_name}
            </Company Name>
            <Product Name>
                {product_name}
            </Product Name>
            <Company details>
                {data}
            </Company details>
        """
    )
    response, industry = await asyncio.gather(
        invoke(
            messages=[
                {"role": "system", "content": PRODUCT_COMPETITOR_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            model="openai/gpt-4.1",
            fallbacks=["anthropic/claude-sonnet-4-latest"],
        ),
        industry_generator(company_name),
    )
    competitor = response.split("<Competitor>")[1].split("</Competitor>")[0].strip()
    competitors = [element.strip() for element in competitor.split("|||")]
    if not competitors or competitors == [""]:
        return None

    async def map_single_competitor(comp):
        """Map a single competitor using the new mapping approach"""
        try:
            company_name_clean = comp.split("~")[0]
            es_id, source = await map_company(
                company_name_clean,
                f"competitors of {product_name} by {company_name}",
                industry,
                client,
                mysql_pool,
                redis_client,
            )
            if es_id and source:
                processed_source = await get_company_source(es_id, source)
                return (comp, es_id, source)
            return (comp, None, None)
        except Exception as e:
            print(f"Error mapping competitor {comp}: {e}")
            return (comp, None, None)

    tasks = [map_single_competitor(comp) for comp in competitors]
    results = await asyncio.gather(*tasks)
    valid_results = [
        (comp, es_ids, es_source)
        for comp, es_ids, es_source in results
        if es_ids is not None and es_source is not None
    ]

    if not valid_results:
        print(f"No competitor companies could be mapped for product: {product_name}")
        return None

    final_dict = {}
    product_data = []
    for comp, es_id, es_source in valid_results:
        li_name = es_source.get("li_name")
        if li_name:
            comp_parts = comp.split("~")
            if len(comp_parts) > 1:
                final_dict[li_name] = comp_parts[1]
                product_data.append((comp_parts[1], es_id, es_source))

    all_product_processing_tasks = []

    for products, es_id, es_source in product_data:
        if products:
            task = asyncio.create_task(
                process_competitors(
                    products, es_id, es_source, product_name, company_name
                )
            )
            all_product_processing_tasks.append(task)

    competitors = await asyncio.gather(*all_product_processing_tasks)
    seen = {}
    for sublist in competitors:
        if sublist is not None:
            for item in sublist:
                if item is not None:
                    key = frozenset(item.items())
                    seen[key] = item

    flattened_competitors = list(seen.values())

    if flattened_competitors:
        asyncio.create_task(
            insert_competitors(
                product_identifier,
                product_name,
                company_identifier,
                company_name,
                flattened_competitors,
            )
        )
        return flattened_competitors

    else:
        return None
