import asyncio, re, tiktoken
from app.utils.qlu2_features.aisearch.utilities.helper_functions.misc_functions import (
    last_converter,
)


async def stream_openai_text_first(text, model="gpt-4", time_delay=2.5):
    emoji_pattern = re.compile(
        "("
        "["
        "\U0001f600-\U0001f64f"
        "\U0001f300-\U0001f5ff"
        "\U0001f680-\U0001f6ff"
        "\U0001f1e0-\U0001f1ff"
        "\U00002700-\U000027bf"
        "\U0001f900-\U0001f9ff"
        "\U00002600-\U000026ff"
        "\U00002b00-\U00002bff"
        "]+"
        ")",
        flags=re.UNICODE,
    )

    def split_on_emojis(text):
        parts = emoji_pattern.split(text)
        return [part for part in parts if part]

    split_parts = split_on_emojis(text)
    enc = tiktoken.encoding_for_model(model)

    chunks = []
    for part in split_parts:
        if emoji_pattern.fullmatch(part):
            chunks.append(part)
        else:
            tokens = enc.encode(part)
            chunks.extend(enc.decode([token]) for token in tokens)

    # Spread over ~3 seconds
    delay = time_delay / max(len(chunks), 1)

    for chunk in chunks:
        await asyncio.sleep(delay)
        yield chunk
    return


async def stream_openai_text(text, model="gpt-4"):
    emoji_pattern = re.compile(
        "("
        "["
        "\U0001f600-\U0001f64f"
        "\U0001f300-\U0001f5ff"
        "\U0001f680-\U0001f6ff"
        "\U0001f1e0-\U0001f1ff"
        "\U00002700-\U000027bf"
        "\U0001f900-\U0001f9ff"
        "\U00002600-\U000026ff"
        "\U00002b00-\U00002bff"
        "]+"
        ")",
        flags=re.UNICODE,
    )

    def split_on_emojis(text):
        parts = emoji_pattern.split(text)
        return [part for part in parts if part]

    split_parts = split_on_emojis(text)
    enc = tiktoken.encoding_for_model(model)
    speed = 0.02

    for part in split_parts:
        if emoji_pattern.fullmatch(part):
            await asyncio.sleep(speed)
            yield part
        else:
            import codecs

            decoder = codecs.getincrementaldecoder("utf-8")()
            tokens = enc.encode(part)
            for token in tokens:
                # decode bytes per token incrementally to avoid U+FFFD artifacts
                b = enc.decode_single_token_bytes(token)
                piece = decoder.decode(b)
                if piece:
                    await asyncio.sleep(speed)
                    yield piece
            tail = decoder.decode(b"", final=True)
            if tail:
                await asyncio.sleep(0.07)
                yield tail
    return


async def sending_grok_results_back(prompt_to_show, response_id=1, time_delay=2):
    async for chunk in stream_openai_text_first(prompt_to_show, time_delay=time_delay):
        return_payload = {
            "step": "text_line",
            "text": chunk,
            "response_id": response_id,
        }
        yield last_converter(return_payload)
