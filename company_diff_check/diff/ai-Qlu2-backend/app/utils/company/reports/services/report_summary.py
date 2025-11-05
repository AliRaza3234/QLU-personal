import os
import re
import asyncio
import numpy as np
from openai import AsyncOpenAI
from fastapi import HTTPException

from app.utils.company.reports.utils.get_blob_data import get_data

from qutils.llm.asynchronous import invoke
from app.utils.company.reports.services.report_prompts import (
    SYSTEM_PROMPT_10K_10Q,
    SYSTEM_PROMPT_DEF14A,
    FINANCIAL_POINTS_DEF14A,
    FINANCIAL_POINTS_10K_10Q,
)

GPT_COST_EFFICIENT_MODEL = "openai/gpt-4o-mini"
GPT_MAIN_MODEL = "openai/gpt-4o-2024-05-13"


def retry_async(max_attempts: int = 3, delay: float = 1.0):
    """Decorator to retry async functions."""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    if attempts >= max_attempts:
                        raise HTTPException(status_code=500, detail=str(e))
                    await asyncio.sleep(delay)

        return wrapper

    return decorator


def cosine_similarity(query_embeddings, embeddings):
    """Calculate cosine similarities for multiple query embeddings against all document embeddings."""
    query_norms = np.linalg.norm(query_embeddings, axis=1, keepdims=True)
    embeddings_norms = np.linalg.norm(embeddings, axis=1)
    query_norms[query_norms == 0] = 1e-10
    embeddings_norms[embeddings_norms == 0] = 1e-10
    dot_product = np.dot(query_embeddings, embeddings.T)
    similarities = dot_product / (query_norms * embeddings_norms)
    return similarities


@retry_async(max_attempts=3, delay=2)
async def generate_embeddings_batch(texts, model="text-embedding-3-large", timeout=120):
    """Generate embeddings for a batch of texts."""
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = await asyncio.wait_for(
        client.embeddings.create(input=texts, model=model), timeout=timeout
    )
    return np.array([np.array(embedding.embedding) for embedding in response.data])


async def batch_generate_embeddings_parallel(
    texts, batch_size=20, model="text-embedding-3-large", timeout=120
):
    """Generate embeddings in parallel for large documents by batching the requests."""

    batches = [texts[i : i + batch_size] for i in range(0, len(texts), batch_size)]
    tasks = [
        generate_embeddings_batch(batch, model=model, timeout=timeout)
        for batch in batches
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    embeddings = []
    for result in results:
        if isinstance(result, Exception):
            print(f"Error in batch processing: {result}")
        else:
            embeddings.extend(result)
    return np.array(embeddings)


@retry_async(max_attempts=3, delay=2)
async def query_embeddings(embeddings, query_points):
    """Calculate cosine similarities for each query point against all document embeddings."""
    query_embeddings = await generate_embeddings_batch(query_points)
    all_similarities = cosine_similarity(query_embeddings, embeddings)
    top_n = min(10, len(all_similarities[0]))
    relevant_chunks_indices = [
        np.argsort(similarities)[-top_n:][::-1] for similarities in all_similarities
    ]

    relevant_chunks = set()
    for indices in relevant_chunks_indices:
        relevant_chunks.update(indices)
    return list(relevant_chunks)


@retry_async(max_attempts=3, delay=2)
async def evaluate_summary(summary: str) -> str:
    """Evaluate the GPT summary to check if it contains relevant information using gpt-4o-mini."""
    evaluation_prompt = f"Evaluate this summary: {summary}. Does it provide relevant financial information? If not, respond with 'empty'. If it provides partial information, list the relevant points only."

    messages = [
        {"role": "system", "content": "You are an expert financial report evaluator."},
        {"role": "user", "content": evaluation_prompt},
    ]

    try:
        evaluation_response = await invoke(
            messages=messages, temperature=0.1, model=GPT_COST_EFFICIENT_MODEL
        )
        return evaluation_response.strip().lower()
    except Exception as e:
        print(f"Evaluation failed: {e}. Retrying with GPT_MAIN_MODEL.")
        evaluation_response = await invoke(
            messages=messages, temperature=0.1, model=GPT_MAIN_MODEL
        )
    return evaluation_response


@retry_async(max_attempts=3, delay=2)
async def summarize_relevant_chunks(relevant_chunks, chunks, form_type="10-K/10-Q"):
    """Generate a summary from the relevant chunks, with prompt based on form type."""
    combined_text = "\n".join(chunks[i] for i in relevant_chunks)

    if form_type == "DEF-14A":
        system_prompt = SYSTEM_PROMPT_DEF14A
    else:
        system_prompt = SYSTEM_PROMPT_10K_10Q

    user_prompt = (
        f"Here is the relevant financial tables from the document: {combined_text}"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response = await invoke(
            messages=messages, temperature=0.1, model=GPT_COST_EFFICIENT_MODEL
        )
        evaluation = await evaluate_summary(response)
        if "empty" in evaluation:
            print("Empty or irrelevant summary, retrying with GPT_MAIN_MODEL")
            response = await invoke(
                messages=messages, temperature=0.1, model=GPT_MAIN_MODEL
            )

    except Exception as e:
        print(f"Exception occurred: {e}. Retrying with GPT_MAIN_MODEL.")
        response = await invoke(
            messages=messages, temperature=0.1, model=GPT_MAIN_MODEL
        )
    return response


@retry_async(max_attempts=3, delay=1)
async def identify_form_type(chunk, blob_name):
    blob = blob_name.lower()
    if (
        "def14a" in blob
        or "def-14a" in blob
        or "def 14a" in blob
        or "proxy statement" in blob
    ):
        return "DEF-14A"
    elif "10-k" in blob or "annual report" in blob:
        return "10-K"
    elif "10-q" in blob or "quarterly report" in blob:
        return "10-Q"

    user_prompt = f"Based on the following text, determine if this is a DEF14A, 10-K, or 10-Q form: {chunk}"

    system_prompt = "You are an expert in financial forms. Identify whether the provided document is a DEF-14A, 10-K, or 10-Q form. Respond only with the form type: DEF-14A, 10-K or 10-Q. "

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response = await invoke(
            messages=messages, temperature=0.1, model=GPT_COST_EFFICIENT_MODEL
        )
    except Exception as e:
        print(e)
        response = await invoke(
            messages=messages, temperature=0.1, model=GPT_MAIN_MODEL
        )

    form_type = response.strip().upper()
    return form_type


async def gen_blob_summary(blob_name, report_link):
    """Main function to generate a summary from the blob URL."""
    try:
        cleaned_content = await get_data(blob_name=blob_name, url=report_link)
        if cleaned_content is None:
            raise HTTPException(status_code=404, detail="Blob not found or empty.")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving blob data: {str(e)}"
        )

    chunk_size = 2000
    overlap_size = 200

    chunks = [
        cleaned_content[i : i + chunk_size]
        for i in range(
            0, len(cleaned_content) - chunk_size + 1, chunk_size - overlap_size
        )
    ]

    embeddings = await batch_generate_embeddings_parallel(chunks, batch_size=50)

    form_type = await identify_form_type(chunks[0], blob_name)

    if form_type == "DEF-14A":
        financial_points = FINANCIAL_POINTS_DEF14A
    else:
        financial_points = FINANCIAL_POINTS_10K_10Q

    relevant_chunks_indices = await query_embeddings(embeddings, financial_points)

    summary = await summarize_relevant_chunks(
        relevant_chunks_indices, chunks, form_type
    )

    filtered_summary = re.sub(r"【.*?】", "", summary)
    filtered_summary = re.sub(r"\*+", "", filtered_summary)
    filtered_summary = "\n".join(
        line.lstrip("- ").strip()
        for line in filtered_summary.splitlines()
        if line.strip()
    )

    return filtered_summary
