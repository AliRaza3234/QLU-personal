INDUSTRIES_EXPANSION_SYSTEM_PROMPT = """
You are an intelligent assistant.

<Instructions>
    You will be provided with all the user's queries in the chat history, along with a "Current Prompt" and a "Past" prompt describing the user's target companies. Your task is to **generate** the most relevant and niche industry keywords based on this input. If a prompt for 'Current' or 'Past' is empty, you will return an empty list for that category.

    A critical constraint to consider is that the keywords you generate will be used in a search system that matches on single words. Your primary goal is to achieve maximum precision and eliminate all false positives.

    Your tasks are:
        1.  **Deconstruct the Input**: First, analyze the `All_user_queries` in conjunction with the `Current Prompt` and `Past` descriptions to identify the distinct core concepts. For example, if the query is for "gaming wearable technology," the core concepts are "gaming" (the market/application) and "wearable technology" (the product form factor).

        2.  **The Rule of Intersection**: You MUST generate industry keywords that exist at the **intersection of ALL core concepts**. A keyword that only satisfies one concept (e.g., generating just "wearables" when the user asked for "gaming wearables") is incorrect and must be discarded. The final keyword must be a logical and direct result of combining all core concepts.

        3.  **The Specificity and Falsification Test**: This is a critical verification step. For every single keyword you consider generating, you must ask: **"Could this keyword accurately describe a company that fulfills only one of the core concepts, but not all of them?"** If the answer is "yes," you MUST discard the keyword. For the "gaming wearable technology" example, the keyword "Gaming Hardware" must be discarded because a company can make gaming hardware (like mice or keyboards) without making wearables. The keyword must be specific enough that it inherently implies all concepts.

        4.  **The Combination Test**: A generic word (like 'Health', 'Digital', 'Consumer') is only acceptable if it is directly combined with another specific keyword that satisfies the user's other core concepts. The generated keyword MUST represent the user's complete, combined idea.

        5.  **Specific Product, Not Broad Category or Component**: You MUST NOT generate keywords that describe a generic *component* (e.g., 'sensors'), a *process* (e.g., 'software development'), a general-purpose *enabling technology* (e.g., 'artificial intelligence'), or a *broad super-category* (e.g., 'Hardware'). The focus must be on the specific, integrated product category defined by the intersection of concepts, not the parts, methods, or overly broad classifications.

        6.  **The Cardinal Rule: Quality Over Quantity**: This is the most important rule. It is better to generate a **shorter list of highly accurate keywords or even an empty list** than to generate imprecise terms. Do not relax the previous rules to meet a quota of 10. Your primary directive is to avoid introducing irrelevant results into the search.
    
    Your focus should only be on the type of industries that the user will be most attracted to. Ignore all other details such as the locations, job titles, skills, etc.
</Instructions>
<Output_format>
    You will return a JSON object enclosed with in <Output> </Output> XML tags. The JSON object will have the following structure:
    <Output>
        {
            "current" : [], # List of up to 10 generated industries that are the most relevant to the companies the user requires in current.
            "past" : [] # List of up to 10 generated industries that are the most relevant to the companies the user requires in past.
        }
    </Output>
    First provide your reasoning for the keywords you are generating. Explain how you deconstructed the user's input and how your choices specifically satisfy ALL rules, especially the "Specificity and Falsification Test" and the "Cardinal Rule." Then provide your output. You always have to return up to 10 niche but highly relevant industries (with each string containing a maximum of 2 keywords).
</Output_format>
    The list of industries should be in the order of relevance. The most relevant industry should be at the top of the list. Remember: Your focus is only on where the person has worked (companies, organizations and industries) NOT the title, skills, locations or any other information.
"""

INDUSTRIES_EXPANSION_USER_PROMPT = """
<Instructions>
    You will be provided with a list of industries and sub industries which are relevant to the companies the user requires, along with all the prompts the user has written in this chat till now.
    
    Your tasks are:
        1. Based on the user's requirements, you need to provide the top 10 most niche and relevant industries or subindustries that the user would require in current and past. If current or past is empty then leave that list as it is. We'll be fetching companies based on the user's requirements from the options given to you. However, as all companies of the industries will be fetched, we need to make sure we don't lose precision so we'll try to ensure niche industries. If less information is given, only focus on the company descriptions.
        2. You can even generate relevant industries which might fit better, avoiding those that are overly broad. For instance, if the user appears to favor AI-focused tech companies, they might be specifically interested in areas like Artificial Intelligence or Machine Learning. In this case, returning "Technology" would overly broaden the search, reducing precision, as it might include companies that are not focused on AI but still fall under the broader technology category. Aim to interpret the user's requirements accurately and provide the most relevant industries while minimizing the risk of identifying the wrong types of companies.
        3. Ensure you find the most niche requirment of the user and expand on that only. For example, if the user said "Get me MLOPs engineer for technology companies" then MLOps suggest ML and AI and such based companies, which are more niche compared to "Technology." Ensure the industries you list have a max of two keywords.
    
    Your focus should only be on the type of industries that the user will be most attracted to. Ignore all other details such as the locations, job titles, skills, etc.

</Instructions>
<Output_format>
    You will return a JSON object enclosed with in <Output> </Output> XML tags. The JSON object will have the following structure:
    <Output>
        {
            "current" : [], # List of top 10 industries that are the most relevant to the companies the user requires in current, , without broadening the search too much.
            "past" : [] # List of top 10 industries that are the most relevant to the companies the user requires in past, without broadening the search too much.
        }
    </Output>

    First provide your reasoning for the industries you are adding. Explain whether the industry covers irrelevant companies as well and they should not reduce precision by adding irrelevant companies. Then provide your output. You always have to return 10 niche but relevant industries (with each string containing a maximum of 2 keywords).
</Output_format>

    The list of industries should be in the order of relevance. The most relevant industry should be at the top of the list. Remember: Your focus is only on where the person has worked (companies, organizations and industries) NOT the title, skills, locations or any other information. 

"""

TITLES_EXPANSION_SYSTEM_PROMPT = """
You are an intelligent assistant whose job is to expand the given titles. Always return a JSON object enclosed within <Output> </Output> XML tags.
"""

TITLES_EXPANSION_USER_PROMPT = """
<Instructions>
    You will be provided with a list of titles that the user has provided, along with all the queries that the user has written in this chat till now. These titles have gotten us 0 results so we need to expand our search further. You need to expand the given titles to include multiple possible variations of the titles that the user might be interested in.

    Your tasks are:
        1. Based on the user's requirements and the titles, expand the current and past titles list to include multiple possible variations of the titles that the user might be interested in. For example, if the user has provided "Software Engineer" then you can expand it to include "Software Developer", "Software Programmer", etc. Or if the user has said "VP of Infrastructure and Data Centers" then "VP of Infrastructure" and "VP of Data Centers" can be included in the list (the original title was broken down), along with full forms and abbreviations (VP, Vice President, etc, all should be included). Always include the original titles as well.
        2. Your main focus should be expanding the titles already selected in the current titles and past titles list, and try not to add titles from previous prompts if they are not included. However, do keep the context in mind. If the current list or past list is empty, then keep it as it is.
        3. You can ignore the other details like the size of the company, location, etc.
</Instructions>
<Output_format>
    Your will return a JSON object enclosed within <Output> </Output> XML tags. The JSON object will have the following structure:
        {
            "current" : [], # List of expanded titles that the user has provided in the current titles list.
            "past": [] # List of expanded titles that the user has provided in the past titles list.
        }
</Output_format>
"""

LOCATIONS_EXPANSION_SYSTEM_PROMPT = """
You are an intelligent assistant whose job is to expand the given locations to include nearby cities, states or metros. Always return a JSON object enclosed within <Output> </Output> XML tags.
"""

LOCATIONS_EXPANSION_USER_PROMPT = """
<Instructions>
    You will be provided with a list of locations that the user has provided. These locations have gotten us 0 results so we need to expand our search further. You need to expand the given locations to include possible cities, metros and states of the locations that the user can also hire from.

    Your tasks are:
        1. Expand the current and past locations list to include multiple locations within 30 miles of the locations provided to you. For example: ***Miami Florida***: ["Miami, Florida", "Miami Beach, Florida", "Coral Gables, Florida", "Doral, Florida", "Hialeah, Florida", "Homestead, Florida", "Key Biscayne, Florida", "North Miami, Florida", "North Miami Beach, Florida", "Aventura, Florida", "Sunny Isles Beach, Florida", "Sweetwater, Florida", "South Miami, Florida", "Miami Lakes, Florida", "Medley, Florida", "Opa-locka, Florida", "West Miami, Florida"] will be returned (with state names included) as the user EXPLICITLY requires nearby regions.
        2. For the state mentioned, retrieve nearby states. For the city mentioned, retrieve nearby cities, and so on. (not outside a country though)
        3. Your main focus should be expanding the locations already selected in the current locations and past locations list, by adding locations within 30 mile radius of each location. Include city names, metros and states. DO NOT go outside the country though (THIS IS A MUST).
</Instructions>
<Output_format>
    Your will return a JSON object enclosed within <Output> </Output> XML tags. The JSON object will have the following structure:
        {
            "current" : [], # List of expanded titles that the user has provided in the current titles list.
            "past": [] # List of expanded titles that the user has provided in the past titles list.
        }
    
    If any of the list contains a whole country, a whole region (bigger than a single country) or a whole continent then return an empty list for that timeline. For example, if current list had ["Lahore, Pakistan", "San Francisco, USA", "India"] then current list would be empty in output because India is a whole country, while the rest are cities. Past would be assessed separately.
</Output_format>
"""


INDUSTRIES_SUGGESTION_SYSTEM_PROMPT = """
You are an intelligent assistant whose job is to get the top 30 ground-level industries or sub industries for current and past both, that seem to be the most relevant to the user and can help narrow down the niche industries. Always return a JSON object enclosed within <Output> </Output> XML tags.
"""

INDUSTRIES_SUGGESTION_USER_PROMPT = """
<Instructions>
    You will be provided with a list of industries and sub industries which are relevant to the companies the user requires, their descriptions, along with all the prompts the user has written in this chat till now. Based on these you have to identify 30 ground-level industries to be shown to the user to get a more niche search.
    
    <important>
        Ground-level industries refer to specific, tangible sectors or products within a broader category, focusing on foundational or concrete applications. For example, within the "wearables" industry, ground-level industries include smartwatches, fitness trackers, smart clothing and many more like these.
    </important> 
    Your tasks are:
        1. Based on the user's requirements, you need to provide the top 30 ground-level industries or subindustries that the user would require in current and past context. If current or past list is empty then leave that list as it is. We'll be asking the user to choose from the options given by you. However, as our goal is to make a more niche search we need to show all the options that fall within the domain of what the user wants.
        2. Avoid industries that are overly broad. For instance, if the user appears to favor AI-focused tech companies, returning "Technology" would overly broaden the search, reducing precision as it might include companies that are not focused on AI but still fall under the broader technology category. Aim to interpret the user's requirements accurately and provide the most relevant industries while minimizing the risk of identifying the wrong types of companies.
        3. You must ensure the industries you list have a max of TWO/2 words. "Cloud Storage Solutions", for example, will become "Cloud Storage", and "Cloud Solution" separately.
    
    Your focus should only be on the ground-level industries, not broad ("consumer electronic" is a very broad search, we'll ask the user to narrow down by asking about smartphones, laptops, gaming consoles, and other options). Ignore all other details such as the locations, job titles, skills, etc.

</Instructions>
<Output_format>
    You will return a JSON object enclosed with in <Output> </Output> XML tags. The JSON object will have the following structure:
    <Output>
        {
            "current" : [], # List of top 30 industries that are the most relevant to the companies the user requires in current, , without broadening the search too much.
            "past" : [] # List of top 30 industries that are the most relevant to the companies the user requires in past, without broadening the search too much.
        }
    </Output>

    First provide your reasoning for the industries you are adding. Explain whether the industries you are showing are truly ground-level industries or not.
</Output_format>
"""

GENERATE_COMPANIES_SYSTEM_PROMPT = """
You are an intelligent assistant tasked with listing down companies according to mentioned requirements. Make sure to strictly follow the output format.
"""

GENERATE_COMPANIES_USER_PROMPT = """
<Instructions>
    - Based on the given prompt generate companies/institutions/organizations based on the context of the query.
    - Only return exact company names, location and industry. 
        - If a tasks mentions specific company names or nouns only, generate those. You are to consider nouns as company names even if you're unfamiliar with them. If they refer to some product or something you are sure isnt a company, they belong to case 4.
        - Any noun mentioned in the prompt is to be considered a company word for word. If you don't know that particular company just give "company name~location~industry" in your output.
            e.g. For the prompt "Apophis"
                **Good Output**: "Apophis~United States~Automotive"
                **Bad Output**: "Apophis~United States~Automotive", "Apple~United States~Automotive" ...
                **Bad Output**: "ApophisTech~United States~Automotive-Pharmaceuticals..", "ApophisFinance~United States" ...
        - This case only caters when only company name(s) is present and not the industry or relevant terms. In case of industry, refer below cases
    - Always try to achieve 50 companies.

</Instructions>

<Output Format>
    - The section after the thought process where the companies are listed down must be enclosed in xml tag of "Companies". The system will fail otherwise
    - Below is the example of required tags in list section:
    <Companies>
        1. Company Name~Location~Industry1~Industry2~industry3
        ...
    </Companies>
</Output Format>

<Important>
    - Generate the most commonly used or known names for the companies. Don't add things like LLC, Ltd, Inc etc.
    - Location can only be country names. If you don't know the location just add 'United States'.
    - Industry will be the two closest industry for that company. 2 is the minimum while 3 is the maximum number of industries.
    - Always treat individual company requirements separately. E.g. "Companies with $500M-$2B in revenue and healthcare companies." here you need to generate companies with $500M–$2B in revenue and companies from healthcare seperately.
    - Once you've given me a company don't give that company again!
    - Dont mention the output format or tags anywhere in the thought process.
    - Even if its being asked not to include a company, DO NOT return that name.
</Important>

<Perform Task>
    - Take a deep breath and understand the instructions. Then tell your thought process and only then generate.
    - Generate a numbered list containing company name and it's location separated by a delimiter '~' Keeping the mentioned prompt in view.
    - After your thought process, add a tag of <Companies> and then generate the list of companies. failing to do so would fail the system.
</Perform Task>
"""
