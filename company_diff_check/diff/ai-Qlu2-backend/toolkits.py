from dotenv import load_dotenv

load_dotenv()

import os
import aiohttp
import asyncio
from mcp.server.fastmcp import FastMCP

mcp = FastMCP()


@mcp.tool()
async def web_search_basic(query: str):
    """Search the web for a query and return only the snippets from Google search results.
    This function does not follow links or scrape full web pages - it only returns the text snippets
    that appear on the Google search results page."""
    max_retries = 3
    base_delay = 1.0  # Base delay in seconds

    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    os.getenv("CLOUDFUNCTION_SERVICE"),
                    params={
                        "query": query,
                        "search_engine": "google",
                        "js_enabled": "true",
                        "caching_enabled": "true",
                        "low_memory": "false",
                    },
                ) as response:
                    return await response.json()
        except Exception as e:
            if attempt == max_retries - 1:  # Last attempt
                raise e
            delay = base_delay * (2**attempt)  # Exponential backoff
            await asyncio.sleep(delay)


if __name__ == "__main__":
    mcp.run()
