import os
import httpx
import asyncio
from fastapi import FastAPI


async def check_company_existence(universal_names, client):
    """
    Checks which companies from a list of universal names exist in Elasticsearch.

    This function queries Elasticsearch to determine which companies from the provided
    list of LinkedIn universal names already exist in the database.

    Args:
        universal_names (list): List of LinkedIn universal names to check
        client: The Elasticsearch client

    Returns:
        list: List of universal names that don't exist in the database
    """
    # Store original names for comparison
    original_names_set = set(universal_names)

    # Query Elasticsearch for companies with the provided universal names
    company_data = await client.search(
        body={
            "_source": ["li_universalname"],
            "query": {"terms": {"li_universalname": universal_names}},
        },
        index=os.getenv("ES_COMPANIES_INDEX"),
        timeout="60s",
    )

    # Extract found company universal names
    found_companies = set()
    if company_data and "hits" in company_data and "hits" in company_data["hits"]:
        for hit in company_data["hits"]["hits"]:
            if "_source" in hit and "li_universalname" in hit["_source"]:
                found_companies.add(hit["_source"]["li_universalname"])

    # Calculate which companies are missing (not found in Elasticsearch)
    missing_companies = original_names_set - found_companies
    return list(missing_companies)


async def ingest_company(universal_name):
    """
    Sends a request to ingest a company with the given LinkedIn universal name.

    This function makes an HTTP POST request to the company generation service
    to trigger the ingestion of a company that doesn't exist in the database.

    Args:
        universal_name (str): The LinkedIn universal name of the company to ingest

    Returns:
        Response object from the HTTP request or None if the request fails
    """
    # Get the company generation service URL from environment variables
    company_generation_url = os.getenv("COMPANY_GENERATION_URL")
    if not company_generation_url:
        return None

    # Make an HTTP POST request to the company generation service
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                company_generation_url,
                json={"universalName": universal_name},
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {os.getenv('COMPANY_INGESTION_AUTH_TOKEN')}",
                },
            )
            return response
        except Exception as e:
            print(f"Error ingesting company {universal_name}: {str(e)}")
            return None


async def enqueue(app: FastAPI, universal_names, client):
    """
    Checks which companies don't exist and adds them to the ingestion queue.

    This function checks which companies from the provided list don't exist in
    Elasticsearch and adds them to the application's ingestion queue for processing.

    Args:
        app (FastAPI): The FastAPI application instance
        universal_names (list): List of LinkedIn universal names to check and potentially queue
        client: The Elasticsearch client
    """
    # Check which companies don't exist in Elasticsearch
    missing_companies = await check_company_existence(universal_names, client)

    # Add missing companies to the ingestion queue if they're not already queued
    for name in missing_companies:
        if name and name not in app.state.ENQUEUED_ITEMS:
            await app.state.INGESTION_QUEUE.put(name)
            app.state.ENQUEUED_ITEMS.add(name)


async def queue_processor(app: FastAPI):
    """
    Processes the ingestion queue by ingesting companies one by one.

    This function runs continuously, taking companies from the ingestion queue
    and sending them to the company generation service for ingestion.

    Args:
        app (FastAPI): The FastAPI application instance
    """
    queue = app.state.INGESTION_QUEUE
    while True:
        # Wait for a company to be added to the queue (with timeout)
        try:
            universal_name = await asyncio.wait_for(queue.get(), timeout=300)
        except asyncio.TimeoutError:
            print("No items arrived in 5 minutes, continuing...")
            continue

        # Process the company
        try:
            await ingest_company(universal_name)
        except Exception as e:
            print(f"Error ingesting company {universal_name}: {e}")
        finally:
            queue.task_done()

        # Add a small delay to prevent overwhelming the system
        await asyncio.sleep(5)


async def start_background_processor():
    """
    Starts the background queue processor task.

    This function creates an asyncio task to run the queue processor in the background.
    """
    asyncio.create_task(queue_processor())


async def scheduled_queue_check():
    """
    Runs a scheduled check of the ingestion queue.

    This function runs continuously, checking the ingestion queue at regular intervals.
    """
    while True:
        try:
            # Wait for 5 minutes before checking again
            await asyncio.sleep(300)
        except Exception as e:
            print(f"Error in scheduled check: {str(e)}")
            # If there's an error, wait for 1 minute before trying again
            await asyncio.sleep(60)


async def init_background_processes(app: FastAPI):
    """
    Initializes background processes for company ingestion.

    This function sets up the ingestion queue, enqueued items set, and starts
    the background tasks for processing the queue and scheduled checks.

    Args:
        app (FastAPI): The FastAPI application instance
    """
    # Initialize application state variables
    app.state.INGESTION_QUEUE = asyncio.Queue()
    app.state.ENQUEUED_ITEMS = set()
    app.state.ACTIVE_TASKS = 0

    # Start background tasks
    app.state.ingestion_task = asyncio.create_task(queue_processor(app))
    app.state.scheduled_check_task = asyncio.create_task(scheduled_queue_check())
