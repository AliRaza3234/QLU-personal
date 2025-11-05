import os
import base64
import aiohttp
import asyncio
from PIL import Image
from io import BytesIO
from collections import Counter
from qutils.websearch import product_image_search
from qutils.llm.asynchronous import invoke
from app.core.database import postgres_insert, postgres_fetch_all


try:
    resample_filter = Image.Resampling.LANCZOS
except AttributeError:
    resample_filter = Image.ANTIALIAS


def post_process_gpt_output(response):
    return (
        response[response[: response.rfind("<")].rfind("<") :]
        .split("<")[1]
        .split(">")[1]
        .strip()
    )


async def find_products_from_gpt(company, linkedin):
    user_message = {
        "role": "user",
        "content": f"""
                    <Instructions>
                        - Give me a comprehensive dictionary of the products and a one liner description for given company: {company} with linkedin: {linkedin}. 
                    </Instructions>

                        
                    <Example>    
                        "Microsoft Office / Office 365": "A suite of productivity applications including Word, Excel, PowerPoint, Outlook, and OneNote, with subscription-based cloud collaboration features.",
                        "Azure": "A cloud computing platform offering infrastructure, services, and solutions for building, deploying, and managing applications.",
                        "Windows": "A widely-used operating system designed for PCs, laptops, and tablets, providing a graphical user interface and productivity tools.",
                        "LinkedIn": "A professional networking platform for job seekers, employers, and professionals to connect, share, and learn.",
                        "Xbox": "A gaming and entertainment platform featuring consoles, games, and services for gaming enthusiasts.",
                        "Microsoft Teams": "A collaboration and communication tool that integrates chat, video conferencing, and file sharing, widely used in business and education.",
                        "OneDrive": "A cloud storage service enabling users to store, sync, and share files across devices securely.",
                        "Outlook": "An email and calendar application for managing personal and professional communications.",
                        "GitHub": "A web-based platform for version control and collaboration, enabling developers to host and review code.",
                        "Bing": "A search engine providing web, image, and video search results powered by Microsoft.",
                        "Microsoft Edge": "A fast and secure web browser offering seamless integration with Microsoft services and enhanced productivity tools.",
                        "Power BI": "A suite of business analytics tools that help visualize data and share insights across an organization.",
                        "Visual Studio": "An integrated development environment (IDE) for developing applications, websites, and services.",
                        "Skype": "A communication tool for voice calls, video calls, messaging, and file sharing.",
                        "Dynamics 365": "A suite of enterprise resource planning (ERP) and customer relationship management (CRM) tools for business management.",
                        "Cortana": "A virtual assistant designed to help users with tasks, reminders, and information through voice and text commands.",
                        "Microsoft Surface": "A line of touchscreen personal computers and interactive whiteboards designed for productivity and creativity.",
                        "Power Automate": "A workflow automation platform to create automated processes across different applications and services.",
                        "Yammer": "An enterprise social network for organizations to foster communication and collaboration.",
                        "Power Apps": "A platform for building custom applications with minimal coding, focused on business and productivity solutions.",
                        "Minecraft": "A popular sandbox video game owned by Microsoft, allowing players to build and explore virtual worlds.",
                        "Stream": "A video service that allows organizations to upload, manage, and share video content securely.",
                        "HoloLens": "A mixed reality headset that blends digital content with the physical world, used in enterprise and research settings.",
                        "Microsoft Defender": "A security platform providing antivirus, firewall, and malware protection features for Windows devices.",
                        "Windows Server": "An operating system designed for server environments, offering features like network management, data storage, and enterprise security.",
                        "Windows PowerShell": "A task automation and configuration management framework consisting of a command-line shell and scripting language.",
                        "System Center": "A suite of system management products for managing IT environments, including servers, storage, and networks.",
                        "Microsoft Bookings": "An appointment scheduling tool designed for businesses to manage and schedule appointments with customers.",
                        "Microsoft To Do": "A task management application that helps users create and manage daily tasks and to-do lists.",
                        "Microsoft Whiteboard": "A digital canvas for real-time collaboration and brainstorming, used by teams to create and share ideas visually.",
                        "Microsoft Planner": "A task management tool that helps teams organize and track their work using visual task boards and to-do lists.",
                        "Microsoft Translator": "A translation tool that supports text, voice, and image translations across multiple languages.",
                        "Microsoft Intune": "A cloud-based service for managing and securing mobile devices, applications, and data.",
                        "Azure Virtual Desktop": "A desktop virtualization service that enables users to access their desktop and applications remotely through the cloud.",
                        "Windows Subsystem for Linux (WSL)": "A compatibility layer for running Linux binary executables natively on Windows.",
                        "Microsoft Sentinel": "A cloud-native SIEM (Security Information and Event Management) solution for managing security incidents and data breaches.",
                        "Azure IoT": "A suite of cloud services for connecting, monitoring, and managing Internet of Things (IoT) devices and solutions.",
                        "Hyper-V": "A hypervisor technology for running virtual machines on Windows Server and Windows operating systems."
                    </Example
                       
                    <Guidelines>
                        - Include only current products directly owned by the company.
                        - Prioritize products with notable historical, cultural, or market impact, ensuring they are widely recognized.
                        - Exclude sub-products / variants.
                        - Provide a comprehensive list of specific products, sorted by popularity, relevance, and impact.
                        - Label past products with adequate information i.e. (Now acquired by ...)  at the end of their name for clarity.
                    </Guidelines>

                    <Format>
                        - You have to provide the results in form of dictionary. With the products as key and description as value.
                        - You must provide the dictionary enclosed in the tags: <products>{{}}</products>
                    </Format>
            """,
    }
    system_message = {
        "role": "system",
        "content": """
                You are Jared who's an expert in finding the products and description for the company given as input.
            """,
    }
    try:
        response = await invoke(
            messages=[system_message, user_message],
            model="openai/gpt-4o",
            fallbacks=["anthropic/claude-sonnet-4-latest"],
            temperature=0,
        )
        return eval(post_process_gpt_output(response))
    except Exception as e:
        print(e)
        return None


async def get_cached_product_info(universalName):
    products_dict = {}
    query = f"""
            select product, info from cache_company_products where li_universalname = '{universalName}'
        """
    results = await postgres_fetch_all(query)
    if not results:
        return None

    for result in results:
        products_dict[result[0]] = result[1]
    company_products = []
    for product, info in products_dict.items():
        company_products.append(
            {
                "product_name": product,
                "info": info,
                "image_url": None,
            }
        )
    return company_products


async def cache_product_info(universalName, products_dict):
    cache_payload = []
    for product, info in products_dict.items():
        escaped_product = product.replace("'", "''")
        escaped_info = info.replace("'", "''")
        cache_payload.append((universalName, escaped_product, escaped_info))
    tasks = []
    for element in cache_payload:
        query = f"""
            INSERT INTO cache_company_products (li_universalname, product, info)
            VALUES ('{element[0]}', '{element[1]}', '{element[2]}')
            """
        tasks.append(postgres_insert(query))
    await asyncio.gather(*tasks)


async def get_cached_product_image(universalName):
    products_dict = {}
    query = f"""
            select product, image_url from cache_company_products where li_universalname = '{universalName}'
        """
    results = await postgres_fetch_all(query)
    if not results:
        return None
    for result in results:
        if result[1]:
            products_dict[result[0]] = result[1]
    if products_dict == {}:
        return None

    return products_dict


async def cache_product_image(universalName, payload):
    tasks = []
    for element in payload["products"]:
        product = element["product_name"]
        escaped_product = product.replace("'", "''")
        image_url = element["image_url"]
        if image_url:
            query = f"""
                UPDATE cache_company_products
                SET image_url = '{image_url}'
                WHERE li_universalname = '{universalName}'
                AND product = '{escaped_product}'
                """

            tasks.append(postgres_insert(query))
    await asyncio.gather(*tasks)


async def get_cached_encoded_image(universalName):
    products_dict = {}
    query = f"""
            select product, encoded_image from cache_company_products where li_universalname = '{universalName}'
        """
    results = await postgres_fetch_all(query)
    if not results:
        return None
    for result in results:
        if result[1]:
            products_dict[result[0]] = result[1]
    if products_dict == {}:
        return None

    return products_dict


async def cache_encoded_image(universalName, payload):
    tasks = []
    for element in payload["products"]:
        product = element["product_name"]
        escaped_product = product.replace("'", "''")
        encoded_image = element["encoded_image"]
        if encoded_image:
            query = f"""
                UPDATE cache_company_products
                SET encoded_image = '{encoded_image}'
                WHERE li_universalname = '{universalName}'
                AND product = '{escaped_product}'
                """

            tasks.append(postgres_insert(query))
    await asyncio.gather(*tasks)


def get_dominant_color(image, k=1):
    small_image = image.resize((50, 50))
    pixels = list(small_image.getdata())
    counter = Counter(pixels)
    most_common_colors = counter.most_common(k)

    return most_common_colors[0][0] if most_common_colors else (255, 255, 255, 255)


async def download_and_resize_image(session, url, icon_size):
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
                print(
                    f"Failed to download image from {url}. HTTP status code: {response.status}"
                )
                return None
    except Exception as e:
        print(f"An error occurred while processing {url}: {e}")
        return None


async def process_images(urls, icon_size):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for idx, url in enumerate(urls):
            tasks.append(download_and_resize_image(session, url, icon_size))

        results = await asyncio.gather(*tasks)
        return results


def image_to_base64(image):
    if not image:
        return None
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    buffered.seek(0)
    img_bytes = buffered.getvalue()
    img_base64 = base64.b64encode(img_bytes).decode("utf-8")
    return img_base64


def safe_int(value):
    if value is None or value == "":
        return None

    try:
        if isinstance(value, float):
            return int(value)

        return int(str(value))

    except ValueError:
        return None


async def company_products_list(universalName, client):
    payload = {"products": []}
    try:
        es_result = await client.search(
            index=os.getenv("ES_COMPANIES_INDEX"),
            body={
                "_source": ["li_name", "li_staffcount", "li_size"],
                "query": {"term": {"li_universalname": {"value": universalName}}},
            },
        )

        if len(es_result["hits"]["hits"]) == 0:
            return {"error": "company name not found"}

        company_name = es_result["hits"]["hits"][0]["_source"]["li_name"]
        li_staffcount = es_result["hits"]["hits"][0]["_source"].get("li_staffcount")
        li_size = es_result["hits"]["hits"][0]["_source"].get("li_size")

        li_size = safe_int(li_size)
        li_staffcount = safe_int(li_staffcount)

        employee_count = 0
        if li_staffcount is not None and li_size is not None:
            employee_count = max(li_staffcount, li_size)
        elif li_staffcount is not None:
            employee_count = li_staffcount
        elif li_size is not None:
            employee_count = li_size
        employee_count = int(employee_count)

        if employee_count < 5000:
            return {"error": "company size less that 5000"}

        company_products = await get_cached_product_info(universalName)
        if not company_products:
            company_products = []
            products_dict = await find_products_from_gpt(company_name, universalName)
            if not products_dict or len(products_dict) == 0:
                return {"error": "failed to get products for this company"}

            for product, info in products_dict.items():
                company_products.append(
                    {
                        "product_name": product,
                        "info": info,
                        "image_url": None,
                    }
                )
            await cache_product_info(universalName, products_dict)
            payload["products"] = company_products
        else:
            payload["products"] = company_products
        product_images = await get_cached_product_image(universalName)
        if not product_images:
            tasks = []
            for element in payload["products"]:
                product = element["product_name"]
                tasks.append(product_image_search(company_name, product))

            results = await asyncio.gather(*tasks)

            index = 0

            for element in payload["products"]:
                element["image_url"] = results[index]
                index += 1

            await cache_product_image(universalName, payload)
        else:

            for element in payload["products"]:
                if element["product_name"] in product_images:
                    element["image_url"] = product_images[element["product_name"]]
                else:
                    result = await product_image_search(
                        company_name, element["product_name"]
                    )
                    element["image_url"] = result
                    temp_payload = {"products": [element]}
                    await cache_product_image(universalName, temp_payload)

        encoded_images = await get_cached_encoded_image(universalName)
        if not encoded_images:
            try:
                image_urls = [element["image_url"] for element in payload["products"]]
                images = await process_images(image_urls, icon_size=(128, 128))
                encoded_images = [image_to_base64(img) for img in images]
                for ind, element in enumerate(payload["products"]):
                    payload["products"][ind]["encoded_image"] = encoded_images[ind]

                await cache_encoded_image(universalName, payload)
            except Exception as e:
                print(e)
        else:
            for element in payload["products"]:
                if element["product_name"] in encoded_images:
                    element["encoded_image"] = encoded_images[element["product_name"]]

                else:
                    if element["image_url"]:
                        image_urls = [element["image_url"]]
                        image = await process_images(image_urls, icon_size=(128, 128))
                        encoded_image = image_to_base64(image[0])

                        element["encoded_image"] = encoded_image
                        temp_payload = {"products": [element]}
                        await cache_encoded_image(universalName, temp_payload)
                    else:
                        element["encoded_image"] = None

        return payload
    except Exception as e:
        print(e)
        return {"error": e}
