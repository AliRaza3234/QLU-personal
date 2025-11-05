async def gpt_cost_calculator_4_turbo(input_tokens: int, output_tokens: int) -> float:
    """
    Asynchronously calculates the estimated cost of running text generation with GPT-4 Turbo model based on token usage.

    This function provides a simple cost estimation model for using the GPT-4 Turbo model, taking into account the
    number of input and output tokens involved in a query. Costs are calculated by specific rates per million tokens,
    with separate rates for input and output tokens.

    Parameters:
        input_tokens (int): The number of tokens used in the input.
        output_tokens (int): The number of tokens generated as output.

    Returns:
        float: The estimated cost in USD for the tokens processed.

    Note:
        The current rate is $10 per million input tokens and $30 per million output tokens.
    """
    input_tokens = (input_tokens / 1000000) * 10
    output_tokens = (output_tokens / 1000000) * 30

    cost = input_tokens + output_tokens
    # print(cost)
    return cost


async def gpt_cost_calculator_35(input_tokens: int, output_tokens: int) -> float:
    """
    Asynchronously calculates the estimated cost of running text generation with the GPT-3.5 model based on token usage.

    This function estimates the cost of using the GPT-3.5 model by accounting for the number of input and output tokens.
    The cost calculation is based on specified rates per million tokens, differentiating between input and output usage.

    Parameters:
        input_tokens (int): The number of tokens used in the input.
        output_tokens (int): The number of tokens generated as output.

    Returns:
        float: The estimated cost in USD for the tokens processed.

    Note:
        The current rate is $0.5 per million input tokens and $1.5 per million output tokens.
    """
    input_tokens = (input_tokens / 1000000) * 0.5
    output_tokens = (output_tokens / 1000000) * 1.5

    cost = input_tokens + output_tokens
    # print(cost)
    return cost
