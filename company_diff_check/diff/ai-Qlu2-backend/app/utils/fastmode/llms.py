import anthropic, os
from qutils.llm.utilities import asynchronous_llm
from app.utils.fastmode.helper_functions import extract_generic
from qutils.openrouter.router import llm_async

client = anthropic.AsyncAnthropic(
    api_key=os.getenv("ANTHROPIC_KEY"),
)


async def grok(messages, model="meta-llama/llama-3.3-70b-instruct"):
    retries = 3
    for i in range(retries):
        try:

            response = await asynchronous_llm(
                messages=messages,
                temperature=0.1,
                model=model,
                provider=provider,
                verbose=False,
                fallback_openai_model="gpt-4.1",
                fallback_anthropic_model="claude-3-5-sonnet-latest",
                max_tokens=4096,
            )
            response = response.replace("null", "None")
            # if check:
            #     print("\n\n", "-" * 50)
            #     print(response)
            #     print("\n\n", "-" * 50)
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

            response = await asynchronous_llm(
                messages=messages,
                temperature=0.1,
                model=model,
                provider=provider,
                verbose=False,
                fallback_openai_model="gpt-4.1",
                fallback_anthropic_model="claude-3-5-sonnet-latest",
                max_tokens=4096,
            )
            response = response.replace("null", "None")
            # print("\n\n", "-"*50)
            # print(response)
            # print("\n\n", "-"*50)
            response = extract_generic(
                "<consistent_question>", "</consistent_question>", response
            )
            return response
        except:
            pass


async def claude(messages, model="claude-3-5-sonnet-latest", retries=3, checking=False):
    for i in range(retries):
        try:
            # if model != "claude-3-5-sonnet-latest":
            # print(messages[0]["content"])
            # message = await client.messages.create(
            #     model=model,
            #     max_tokens=8192,
            #     temperature=0,
            #     messages=messages,
            # )
            # response = message.content[0].text
            response = await asynchronous_llm(
                messages=messages,
                temperature=0.1,
                model=model,
                provider="anthropic",
                verbose=False,
                fallback_openai_model="gpt-4.1",
                max_tokens=4096,
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
            response = await asynchronous_llm(
                messages=messages,
                temperature=0.1,
                model="llama-3.3-70b-versatile",
                provider="groq",
                verbose=False,
                fallback_openai_model="gpt-4.1",
                fallback_anthropic_model="claude-3-5-sonnet-latest",
                max_tokens=4096,
            )
            response = response.replace("null", "None")
            response = extract_generic("<Output>", "</Output>", response)
            final_response = eval(response)
            final_response["model"] = "grok"
            return final_response
        except Exception as e:
            print("Exception\n", e)
            pass
