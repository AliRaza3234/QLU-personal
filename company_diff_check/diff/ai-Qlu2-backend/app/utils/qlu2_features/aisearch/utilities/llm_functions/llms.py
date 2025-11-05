from app.utils.qlu2_features.aisearch.utilities.helper_functions.misc_functions import (
    extract_generic,
)

from qutils.llm.asynchronous import invoke, stream


async def grok(messages, model="meta-llama/llama-3.3-70b-instruct"):
    retries = 3
    for i in range(retries):
        try:

            response = await invoke(
                messages=messages,
                temperature=0.1,
                model="groq/llama-3.3-70b-versatile",
                fallbacks=["groq/openai/gpt-oss-120b", "openai/gpt-4.1"],
            )
            response = response.replace("null", "None")
            response = extract_generic("<Output>", "</Output>", response)
            final_response = eval(response)
            if isinstance(final_response, dict):
                final_response["model"] = "grok"
            return final_response
        except:
            pass


async def grok_rewritten(
    messages, model="meta-llama/llama-3.3-70b-instruct", provider="groq"
):
    retries = 3
    for i in range(retries):
        try:

            response = await invoke(
                messages=messages,
                temperature=0.1,
                model="groq/llama-3.3-70b-versatile",
                fallbacks=["groq/openai/gpt-oss-120b", "openai/gpt-4.1"],
            )
            response = response.replace("null", "None")
            response = extract_generic(
                "<consistent_question>", "</consistent_question>", response
            )
            return response
        except:
            pass


async def grok_rewritten_stream(
    messages, model="meta-llama/llama-3.3-70b-instruct", provider="groq"
):
    retries = 3
    start_tag = "<consistent_question>"
    end_tag = "</consistent_question>"
    for attempt in range(retries):
        try:
            started = False
            buf = ""
            async for chunk in stream(
                messages=messages,
                temperature=0.1,
                model="groq/llama-3.3-70b-versatile",
                fallbacks=["groq/openai/gpt-oss-120b", "openai/gpt-4.1"],
            ):
                if not chunk:
                    continue
                buf += chunk
                if not started:
                    i = buf.find(start_tag)
                    if i != -1:
                        buf = buf[i + len(start_tag) :]
                        started = True
                if started:
                    j = buf.find(end_tag)
                    if j != -1:
                        to_emit = buf[:j]
                        if to_emit:
                            yield to_emit
                        return
                    # Emit safe prefix while keeping a small tail for boundary detection
                    keep = len(end_tag) - 1
                    if len(buf) > keep:
                        to_emit, buf = buf[:-keep], buf[-keep:]
                        if to_emit:
                            yield to_emit

            if started:
                raise RuntimeError(
                    "Stream ended before end_tag </consistent_question>."
                )
            else:
                raise RuntimeError(
                    "Start tag <consistent_question> not found in stream."
                )
        except Exception:
            if attempt == retries - 1:
                raise
            continue


async def claude(
    messages, model="anthropic/claude-3-5-sonnet-latest", retries=3, checking=False
):
    for i in range(retries):
        try:
            response = await invoke(
                messages=messages,
                temperature=0.1,
                model=model,
                fallbacks=["anthropic/claude-3-7-sonnet-latest", "openai/gpt-4.1"],
            )
            response = response.replace("null", "None")
            if checking:
                print("\n\n", "-" * 50)
                print(response)
                print("\n\n", "-" * 50)
            response = extract_generic("<Output>", "</Output>", response)
            final_response = eval(response)
            return final_response
        except Exception as e:
            print(e)
            pass


async def claude_with_system(
    messages, model="claude-3-7-sonnet-latest", SYSTEM_PROMPT="", retries=3
):
    return ""
    for i in range(retries):
        try:
            # message = await client.messages.create(
            #     model=model,
            #     max_tokens=8192,
            #     temperature=0,
            #     system=SYSTEM_PROMPT,
            #     messages=messages,
            # )
            # response = message.content[0].text
            if SYSTEM_PROMPT:
                messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
            response = await asynchronous_llm(
                messages=messages,
                temperature=0.1,
                model=model,
                provider="anthropic",
                verbose=False,
                fallback_openai_model="gpt-4.1",
                max_tokens=4096,
            )
            final_response = ""
            try:
                if "<verdict>" in response:
                    verdict_score = extract_generic("<verdict>", "</verdict>", response)
                    if verdict_score:
                        verdict_score = verdict_score.split("~")
                        if len(verdict_score) == 2:
                            verdict = verdict_score[0]
                            score = verdict_score[1]

                            if "true" in verdict.lower():
                                if int(score) > 7:
                                    final_response = extract_generic(
                                        "<question>", "</question>", response
                                    )
            except:
                final_response = ""

            # else:
            #     response = response.replace("null", "None")
            #     response = extract_generic("<Output>", "</Output>", response)
            #     final_response = eval(response)
            return final_response
        except Exception as e:
            print(e)
            pass


async def grok_with_system(messages, SYSTEM_PROMPT):

    messages = [{"role": "system", "content": SYSTEM_PROMPT}, messages[0]]

    retries = 3
    for i in range(retries):
        try:
            response = await invoke(
                messages=messages,
                temperature=0.1,
                model="groq/llama-3.3-70b-versatile",
                fallbacks=["groq/openai/gpt-oss-120b", "openai/gpt-4.1"],
            )
            response = response.replace("null", "None")
            response = extract_generic("<Output>", "</Output>", response)
            final_response = eval(response)
            final_response["model"] = "grok"
            return final_response
        except Exception as e:
            print("Exception\n", e)
            pass


async def call_llama_70b(messages, temperature, model="groq/llama-3.3-70b-versatile"):
    retries = 3
    for i in range(retries):
        try:
            response = await invoke(
                messages=messages,
                temperature=temperature,
                model="groq/llama-3.3-70b-versatile",
                fallbacks=["groq/openai/gpt-oss-120b", "openai/gpt-4.1"],
            )
            return response
        except:
            pass
    print("LLM Call Failed!")
    return None


async def call_gpt_oss_120b(messages, temperature, model="groq/openai/gpt-oss-120b"):
    retries = 3
    for i in range(retries):
        try:
            response = await invoke(
                messages=messages,
                temperature=temperature,
                model="groq/openai/gpt-oss-120b",
                fallbacks=["openai/gpt-4.1", "anthropic/claude-sonnet-4-20250514"],
            )
            return response
        except:
            pass
    print("LLM Call Failed!")
    return None


async def call_claude_sonnet(
    messages, temperature, model="anthropic/claude-sonnet-4-20250514"
):

    retries = 3
    for i in range(retries):
        try:
            response = await invoke(
                messages=messages,
                temperature=temperature,
                model="anthropic/claude-sonnet-4-20250514",
                fallbacks=["anthropic/claude-3-7-sonnet-latest", "openai/gpt-4.1"],
            )
            return response
        except:
            pass
    print("LLM Call Failed!")
    return None


async def call_gpt_4_1_with_processing(
    messages, temperature=0.1, model="openai/gpt-4.1"
):
    retries = 3
    for i in range(retries):
        try:
            response = await invoke(
                messages=messages,
                model="openai/gpt-4.1",
                temperature=0.1,
                fallbacks=["anthropic/claude-sonnet-4-20250514", "openai/gpt-4o"],
            )
            response = extract_generic("<Output>", "</Output>", response)
            final_response = eval(response)
            return final_response
        except:
            pass
    print("LLM Call Failed!")
    return None


async def call_gpt_4_1(messages, temperature, model="openai/gpt-4.1"):
    retries = 3
    for i in range(retries):
        try:
            response = await invoke(
                messages=messages,
                model="openai/gpt-4.1",
                temperature=0.1,
                fallbacks=["anthropic/claude-sonnet-4-20250514", "openai/gpt-4o"],
            )

            return response
        except:
            pass
    print("LLM Call Failed!")
    return None


async def call_gpt_4_1_mini(messages, temperature, model="openai/gpt-4.1-mini"):
    retries = 3
    for i in range(retries):
        try:
            response = await invoke(
                messages=messages,
                model="openai/gpt-4.1-mini",
                temperature=0.1,
                fallbacks=["groq/openai/gpt-oss-120b", "openai/gpt-4.1"],
            )
            return response
        except:
            pass
    print("LLM Call Failed!")
    return None


async def call_groq_llama_scout(messages, temperature):
    retries = 3
    for i in range(retries):
        try:
            response = await invoke(
                messages=messages,
                temperature=temperature,
                model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
                fallbacks=["groq/openai/gpt-oss-120b", "openai/gpt-4.1-mini"],
            )
            return response
        except:
            pass
    print("LLM Call Failed!")
    return None


async def call_gpt_oss_20b(messages, temperature):
    retries = 3
    for i in range(retries):
        try:
            response = await invoke(
                messages=messages,
                temperature=temperature,
                model="groq/openai/gpt-oss-20b",
                fallbacks=[
                    "groq/meta-llama/llama-guard-4-12b",
                    "groq/openai/gpt-oss-120b",
                ],
            )
            return response
        except:
            pass
    print("LLM Call Failed!")
    return None
