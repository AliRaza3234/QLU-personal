import requests
from bs4 import BeautifulSoup
import asyncio
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.content_filter_strategy import BM25ContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
import re

import os
import httpx

from dotenv import load_dotenv


from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import sys


async def get_top_google_results(query, num_results=5):
    """
    Fetch the top URL pages from Google search results for a given query without using an API.

    Args:
        query (str): Search query.
        num_results (int): Number of top results to fetch (default: 5).

    Returns:
        list: A list of URLs of the top search results.
    """
    # Encode the query for the URL
    query = query.replace(" ", "+")
    google_url = f"https://www.google.com/search?q={query}&num={num_results}"

    # Set user-agent to mimic a browser
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
    }

    # Send a GET request to Google
    response = requests.get(google_url, headers=headers)
    response.raise_for_status()

    # Parse the response with BeautifulSoup
    soup = BeautifulSoup(response.text, "html.parser")

    # Extract URLs from search results
    urls = []
    for g in soup.find_all("div", class_="tF2Cxc"):  # Google search result containers
        link = g.find("a", href=True)
        if link and link["href"]:
            urls.append(link["href"])
            if len(urls) == num_results:
                break

    return urls


async def crawl_url(url, query):
    """
    Crawl a single URL asynchronously and return the result.
    """
    bm25_filter = BM25ContentFilter(
        user_query=query,
        bm25_threshold=1.2,
    )

    md_generator = DefaultMarkdownGenerator(content_filter=bm25_filter)

    config = CrawlerRunConfig(
        markdown_generator=md_generator,
        word_count_threshold=10,
        excluded_tags=["nav", "footer", "header"],
        exclude_external_links=True,
        exclude_external_images=True,
        process_iframes=True,
        remove_overlay_elements=True,
    )

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url, config=config)
        return result


async def process_chunking(result):
    """
    Process chunking for markdown content asynchronously.
    """
    chunker = SlidingWindowChunking(window_size=100, step=80)
    return chunker.chunk((remove_all_urls(result.markdown_v2.fit_markdown)))


class SlidingWindowChunking:
    def __init__(self, window_size=400, step=350):
        self.window_size = window_size
        self.step = step

    def chunk(self, text):
        words = text.split()
        chunks = []
        for i in range(0, len(words) - self.window_size + 1, self.step):
            chunks.append(" ".join(words[i : i + self.window_size]))
        return chunks


async def crawl_and_chunk(urls, query):
    tasks = [crawl_url(url, query) for url in urls]
    results = await asyncio.gather(*tasks)

    chunking_tasks = []
    for result in results:
        if result.success:
            print(f"Markdown for {result.url} (BM25 query-based): was SUCCESSFULL")
            print(result.markdown)
            print("-" * 47)

            # Chunking process in parallel
            chunking_tasks.append((process_chunking(result)))
        else:
            print(f"Error crawling {result.url}: {result.error_message}")

    chunks_results = await asyncio.gather(*chunking_tasks)
    chunked_strings = []

    for chunks in chunks_results:
        # print("-" * 26, "List of Chunks", "-" * 26)
        # print("-" * 46)
        index = 0
        for chunk in chunks:
            chunked_strings.append(chunk)
            index += 1
            # print("-" * 26, index, "-" * 26)
            # print(chunk)
    return chunked_strings


_ = load_dotenv()


async def get_source_from_pegasus(params):
    pegasus_url = os.getenv("CLOUDFUNCTION_SERVICE")
    headers = {"accept": "application/json"}
    async with httpx.AsyncClient(timeout=300) as client:
        try:
            response = await client.get(pegasus_url, headers=headers, params=params)
            response.raise_for_status()
            json_response = response.json()
            return json_response
        except httpx.HTTPStatusError as http_err:
            status_code = http_err.response.status_code
            print(f"Status code: {status_code}")
            return None
        except httpx.RequestError as req_err:
            print(f"Request error occurred: {str(req_err)}")
            return None
        except Exception as e:
            print(f"Exception: {e}")
            return None


def remove_all_urls(text):
    # Define a regex pattern to match URLs (http, https, and other common formats)
    pattern = r"https?://[^\s]+|www\.[^\s]+"

    # Use re.sub() to replace matched URLs with an empty string
    cleaned_text = re.sub(pattern, "", text)

    return cleaned_text


async def main(query, urls):
    if not urls:
        print("No URLs provided.")
        return

    print("Crawling and processing URLs in parallel...")
    crawled_chunks = await crawl_and_chunk(urls, query)
    extractor = CosineSimilarityExtractor(query)
    relevant_chunks = extractor.find_relevant_chunks(crawled_chunks)
    print("-" * 26, " Printing Relevant Chunks ", "-" * 26)
    print(len(relevant_chunks), len(crawled_chunks))
    for chunk in relevant_chunks[:5]:
        print("-" * 47)
        print(chunk)


class CosineSimilarityExtractor:
    def __init__(self, query):
        self.query = query
        self.vectorizer = TfidfVectorizer()

    def find_relevant_chunks(self, chunks):
        vectors = self.vectorizer.fit_transform([self.query] + chunks)
        similarities = cosine_similarity(vectors[0:1], vectors[1:]).flatten()
        return [(chunks[i], similarities[i]) for i in range(len(chunks))]


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python crawl.py <query>")
        sys.exit(1)

    query = sys.argv[1]

    pegasus_result = asyncio.run(get_source_from_pegasus(params={"query": query}))

    urls_list = []
    for result in pegasus_result["query_result"][:5]:
        urls_list.append(result["link"])
        print(result)

    if not urls_list:
        print("No results found.")
        sys.exit(1)

    print("Top 5 URLs:")
    for idx, url in enumerate(urls_list, start=1):
        print(f"{idx}: {url}")

    # Run the crawl and chunking in parallel
    asyncio.run(main(query=query, urls=urls_list))
