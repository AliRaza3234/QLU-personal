from copy import deepcopy
from app.utils.dialer.utils.metric_utils.metric_utils_prompts import (
    METRIC_EVAL_USER_PROMPT,
    METRIC_EVAL_SYSTEM_PROMPT,
    METRIC_COMPARISON_SYSTEM_PROMPT,
)
from app.utils.dialer.utils.gpt_utils.gpt_runner import gpt_runner

# GPT_MAIN_MODEL = os.getenv("GPT_MAIN_MODEL")
GPT_MAIN_MODEL = "gpt-4o"


async def compareMetrics(objectOne: str, objectTwo: str) -> str:
    """
    Function to compare two metric objects, remove any duplicates and return one final set of metrics

    Args:
    - objectOne (str): Json like string for first set of metrics
    - objectTwo (str): Json like string for second set of metrics

    Returns:
    - str: Final set of metrics in json like string
    """
    systemPrompt = deepcopy(METRIC_COMPARISON_SYSTEM_PROMPT)
    userPrompt = """
    Given the following two json objects, understand and compare them and merge them such that
    there are no more than 6 metrics. There can be less than 6 if they are two overlapping or not good.

    Object One = {objectOne}

    Object Two = {objectTwo}
    """
    userPrompt = userPrompt.format(objectOne=objectOne, objectTwo=objectTwo)
    chat = [
        {"role": "system", "content": systemPrompt},
        {"role": "user", "content": userPrompt},
    ]
    response = await gpt_runner(
        chat, temperature=0.1, model=GPT_MAIN_MODEL, json_format=True
    )
    return response


async def getFinalMetrics(text: str, category: str, metrics: str) -> str:
    """
    Function that evaluates and returns the final set of metrics that would be most sensible to use
    to evaluate a text of a particular category

    Args:
    - Text (str): A piece of text belonging to the specific category
    - Category (str): Specific intent for which metrics are to be evaluated
    - Metrics (str): Json like string containing metrics that are to be evaluated and finalised

    Returns:
    - str: Final set of metrics in json like string
    """
    systemPrompt = deepcopy(METRIC_EVAL_SYSTEM_PROMPT)
    userPrompt = deepcopy(METRIC_EVAL_USER_PROMPT)
    userPrompt = userPrompt.format(message=text, category=category, metrics=metrics)
    chat = [
        {"role": "system", "content": systemPrompt},
        {"role": "user", "content": userPrompt},
    ]
    response = await gpt_runner(
        chat, temperature=0.1, model=GPT_MAIN_MODEL, json_format=True
    )
    return response


def parsing_metrics(metrics: str, is_fetched: bool) -> str:
    """
    Helper function to parse and convert JSON-like strings into acceptable postgres format
    """
    if is_fetched:
        metrics = str(metrics)
        metrics = metrics.replace("'", '"')
    else:
        newMetrics = {}
        # print(metrics)
        # metrics = json.loads(metrics)
        for key, value in metrics.items():
            new_key = key.replace("'", "")
            new_value = value.replace("'", "")
            newMetrics[new_key] = new_value
            # metrics[key] = metrics[key].replace("'", "")
        metrics = str(newMetrics)
        metrics = metrics.replace("'", '"')
    return metrics
