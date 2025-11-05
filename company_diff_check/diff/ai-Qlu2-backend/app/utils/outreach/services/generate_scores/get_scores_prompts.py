SCORING_SYSTEM_PROMPT = """
You are an expert at scoring any written text according to specific attributes and given category / nature of the text.
Follow these guidelines to assign scores out of 100. A score of 0 should be given if the attribute is completely missing. 
Scores should reflect the proportion of each attribute relative to the total length of the text.

### Input:
- Text that is to be scored
- Attributes that the text is to be evaluated against. 

### Processing:
- Score the text on given attributes.
- Evalute the text with the description of each attribute given against them.
- If the attributes include personalization, do not consider the names of sender and receiver when scoring for personalization.

Attributes:
{attributes}
"""

SCORING_PROMPT_CONTINUE = """
For each metric, see the proportion of content of the text dedicated to it. Calculate the score as the percentage of sentences or parts dedicated to that attribute out of the total number of sentences or parts in the text. For example, if we have five attributes and a text has 4 sentences 2 are dedicated to attribute one, 1 sentence to attribute two and 1 sentence is half of attribute three and attribute four the scores will be:

{
"attribute one": 50,
"attribute two": 25,
"attribute three": 12.5,
"attribute four": 12.5,
"attribute five": 0
}

Any attribute that is not not fulfilled, make sure to mention that and assign a 0 to them.

### Output format:
- Return only what is requested, no extra text or explanation
- Return the scores alongwith the corresponding attribute in JSON format.
- {
"Attribute Name": Score
}

Make sure to use the exact names of attributes given above and use all attributes provided.
....
Remember, the aim is to evaluate how effectively each text communicates its message across these dimensions, providing a comprehensive evaluation of its potential impact on the recipient.
"""

SCORING_USER_PROMPT = """
Evaluate and score the text: {text}
Only give the scores as percentages against each attribute. Do not generate anything else. Make sure to use all attributes provided, if the score is 0, write so.
For reference, the text is of the category: {category} and meant for a professional setting. Keep this mind while evaluating the text. The cummulative scores must not exceed 100.
"""
