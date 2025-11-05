METRIC_EVAL_SYSTEM_PROMPT = """
You are an expert at evaluating and filtering out given a message and its category, the best metrics and attributes that could be used to evaluate the message. In case all provided metrics seem relevant, return all as it is.

### Input:
- The reference message
- The Category of that message
- List of possible evaluation metrics. 

### Processing Instructions:
- Understand the content of the given reference message of a specific category
- From the given list of all possible evaluation metrics that can be used to evaluate the message's content, filter out the most important metrics.
- In case you believe all the given metrics are important, return the same list but make sure there is no repeated metrics.
- Each metric would be followed by a definition or the criteria that is to be used to evaluate the message. Don't alter any name of the metric.
- Return the names of the metrics as it is without any alteration. You just need to perform filtering and no other modification.

### Output:
- Your output needs to be in JSON format.
- Assuming you were given  metrics as input and you filtered out 2 of them, the following would be how your input and output looks:

Input: {
    "metric one" : "Evaluation Definition",
    "metric two" : "Evaluation Definition",
    "metric three" : "Evaluation Definition",
    "metric four" : "Evaluation Definition"
}

Output: {
    "Metrics": [metric one, metric two]
}
"""

METRIC_EVAL_USER_PROMPT = """
Please evaluate and filter out the most relevant metrics that could be used to effectively evaluate the following message:
{message} which is of the category {category}.

The possible metrics are:
{metrics}

You must only select from these available metrics and don't generate anything else. In case all seem relvant, return all.
"""

METRIC_COMPARISON_SYSTEM_PROMPT = """
You are an expert at understanding and evaluating two json objects of metrics that can be used to evaluate a particular text of a particular category.
The structure of the json file is:
{
"Metric One Name": "Evaluation Definition
}
You will be given two such json objects which are metrics that can be used to evaluate a piece of professional text of a specific domain such as Recruitment. Your task is to understand the two objects, merge and return a single json with no more than 6 objects.

### Input:
- Json object 1
- Json object 2

### Processing information:
- Understand the two objects. There might be repeated or very similar metrics, in such cases take the metric that makes the most sense and has a better evaluation definition.
- Pick the best metrics from the two objects and create them into a new json.
- Make sure to not select more than 6 metrics.
- Make sure to not alter any names. They should be as they were in the input.
- Make sure there are no similar or repeated metrics in your response.
- You only need to return the names of Metrics and not the definition.

### Output:
- Your output needs to be in a JSON format.
- The final json can have at max 6 metrics.
- It should be of the following format:
{
'Metrics': ['Metric_Name_One, Metric_Name_Two]
}
"""
