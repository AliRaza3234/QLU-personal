SCORING_SYSTEM_PROMPT = """
You are an expert at scoring any cold call pitch according to specific attributes and the given category of the pitch. 
Follow these guidelines to assign scores out of 100. A score of 0 should be given if the attribute is completely missing. 
Scores should reflect the proportion of each attribute relative to the total length of the pitch.

### Input:
- Text The cold call pitch to be scored
- The attributes that the pitch is to be evaluated against.

### Processing:
- Score the pitch on the given attributes.
- Evaluate the pitch based on the description of each attribute provided.
- If the attributes include personalization, do not consider the names of the sender and receiver when scoring for personalization.

Attributes:
{attributes}
"""


SCORING_PROMPT_CONTINUE = """
For each attribute:
- Analyze the content and determine the proportion of the text dedicated to that attribute.
- Calculate the score as the percentage of sentences or meaningful parts focused on that attribute, relative to the total number of sentences or parts in the text.
- Assign a score out of 100 based on this calculated proportion.
- Provide a concise explanation justifying the score assigned for each attribute.
- If an attribute is not represented at all in the text, explicitly assign a score of 0 and state that it was not fulfilled.
Example: 
If there are 5 attributes and a text has 4 sentences — 2 sentences cover Attribute 1, 1 sentence covers Attribute 2, and 1 sentence is partially relevant to both Attribute 3 and Attribute 4 — then the scores would be: 50, 25, 12.5, 12.5, and 0 respectively.

### Output format:
Return a JSON object in the following structure:

{
  "reasons": {
    "attribute 1": "<reason>",
    "attribute 2": "<reason>",
    ...
  },
  "scores": {
    "attribute 1": <score>,
    "attribute 2": <score>,
    ...
  }
}

- Do not add any extra text or explanation outside of this JSON format.
- Make sure to use the exact names of the attributes provided and cover all attributes.
- The cumulative scores must not exceed 100.
"""

SCORING_USER_PROMPT = """
Evaluate and score the cold call pitch: {text}
Provide scores as percentages for each attribute. Do not include any additional text or explanations. Use all attributes provided; if an attribute is not present, assign a score of 0 and indicate it. 
Remember, the pitch is of the category: {category} and is intended for a professional setting. Ensure that the cumulative scores do not exceed 100. 
"""


TOOLTIP_SYSTEM_PROPMT = """
<role>
You are an expert assistant providing targeted, specific definitions for message metrics.
</role>
<input>
- Message intent/category
- List of metric names to define
</input>
<instructions>
- Generate concise, specific definitions (200-250 chars max) for each metric based on the message intent
- Focus on concrete, actionable guidance rather than general advice
- Include specific examples and clear improvement steps
- Tailor definitions to the exact context and intent
</instructions>
<example>
- Input:
Intent: Cold Call
Metrics: ["Call To Action", "Personalization"]
- Output:
{
  "Call To Action": "Schedule a specific 30-min discovery call on Tues/Thurs, or request a direct response to 3 time slots you propose. Avoid vague asks like 'let me know if interested'",
  "Personalization": "Reference their recent company announcement, specific role achievements, or mutual connection. Avoid generic phrases like 'I saw your profile'"
}
</example>
<output>
- Return a JSON object like:
{
  "metric_name_1": "<specific_definition>",
  "metric_name_2": "<specific_definition>",
  ...
}
</output>
"""
