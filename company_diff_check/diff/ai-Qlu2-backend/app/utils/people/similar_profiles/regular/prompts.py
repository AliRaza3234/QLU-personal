GET_BASE_PRODUCT_SYSTEM_PROMPT = """
You are an intelligent assistant named Jared.
"""

GET_BASE_PRODUCT_USER_PROMPT = """
<Instructions>
- Your job is to look at a job title, job description, headline and the company of a person and give me the product or service that person might belong to.
- Do not add company name in the product or service. If the company name is present in the product or service then remove it. Like for Samsung Gear, just give Gear.
</Instructions>

<Important Instruction>
- If no product or service can be deduced from the data then just give "NO_PRODUCTS".
- Product or service names are proper nouns, acronyms, or specific phrases like "Windows", "Pixel", "AWS", "Oculus" etc.
- These names will be extracted only if they are explicitly mentioned in the provided data. Don't infer on your own.
</Important Instruction>

<Output Format>
- First think about the problem and then give your output enclosed within <predict> </predict> tags.
</Output Format>
"""

GET_INDUSTRY_SYSTEM_PROMPT = """
Your name is Jared and you are an expert in identifying at the working industry of a person.
"""

GET_INDUSTRY_USER_PROMPT = """
Your name is Jared and you are an expert in identifying at the working industry of a person.

<Instructions>
- Given a person's data and his/her company determine the industry in which that person works in.
- You can only give medium or ground level industries not high level. For example Consumer Eletronics is a high level industry whereas Cell Phones is a medium level and Andriod or IoS smartphone may be ground.
- I'll use the industries that you give to keyword match in LinkedIn's company industry and sub-industry data and find the most relevant companies so there is very little room for error.
- The industry can't be more than 2 words.
- Use the profile data to determine the company industry not any profile keywords.
- After you've infered the industries to target create multiple variations of that industry string. For example Wearables can also be Wearable, Wearable Technology etc.
- You can further drill down ground level industries to get multiple keywords. For example Smart Watches is a wearable worn on the hand so other such wearables can also be relevant keywords.
</Instructions>


<Output Format> 
- First give at least 50 reasoning tokens or more.
- Then provide your final output enclosed within: 

<output> 
["industry 1", "industry 2", ...]
</output>
</Output Format>
"""

RELATIVE_EXPERIENCE_SYSTEM_PROMPT = """Your name is Jared and you are an expert in identifying most functional expereince"""

RELATIVE_EXPERIENCE_USER_PROMPT = """    
<Instructions>
- Given a person multiple experiecne, you have find most highest rank wise and functional wise experience.
- You will return experience the index of the which has most highest rank and functional wise.

</Instructions>

<Output Format>
- First think about the problem and then give the relevant experience index enclosed within <output> [experience_index] </output> tags.
- If you think the problem is not solvable, then return <output> [0] </output> tags.
- If there are multiple experiences with same rank and functional wise, then return multiple indexes separated by comma enclosed within <output> [experience_index1, experience_index2] </output> tags.
</Output Format>
"""

RELATIVE_EXPERIENCE_GROUP_RANK_SYSTEM_PROMPT = """Your name is Jared and you are an expert in identifying most relevant expereince based on given data"""

RELATIVE_EXPERIENCE_GROUP_RANK_USER_PROMPT = """    
<Instructions>
- Given a person multiple experiecne, you have find most relevant experience based on given filters.
- You will return experience the index of the which has most relevant rank and functional area.

</Instructions>

<Output Format>
- First think about the problem and then give the relevant experience index enclosed within <output> [experience_index] </output> tags.
- If you think the problem is not solvable, then return <output> [0] </output> tags.        
</Output Format>
"""


FUNCTION_KEYWORDS_SYSTEM_PROMPT = """
You are an intelligent assistant.
"""

FUNCTION_KEYWORDS_USER_PROMPT = """
<Instructions>
- Given a person's LinkedIn profile data, extract the following:
- **Rank**: Identify the rank or position level from the title. For example, in "Director of Engineering," the rank is "Director."
- **Core Functional Areas**: Extract keywords that are most commonly used in job titles, such as "Engineering" or "Technology." These will be used for strict substring matching in titles combined with the rank.
- **Secondary Functional Areas**: Extract additional keywords or industry-specific terms that can help in loosely matching and better sorting of profiles. Examples include "BFSI," "Banking," or "Finance."

- Ensure that core functions are terms frequently found in job titles and represent primary domains of work or specialization.
- If the title or headline contains multiple functional areas or keywords, list each separately, ensuring they represent distinct departments or specializations.
- If the keywords are not explicitly mentioned in the title or headline, do not infer them.
- Core functions are used to strict keyword match profiles in a database so these can't be really niche.
</Instructions>

<Examples>
- For the data:
- **Title**: "Director"
- **Headline**: "Chief Technology Officer - BFSI vertical, Microsoft"

The correct extraction would be:
{{
"rank": ["Director", "Chief Technology Officer"],
"core": ["Technology"],
"secondary": ["BFSI", "Banking", "Finance"]
}}
</Examples>

<Very Important Instruction>
- "rank" and "core" are used to match profiles in LinkedIn titles only if both of those words exist. Keep this in mind! If you think both those words might not exist in together in a title then shift "core" to "secondary".
</Very Important Instruction>

<Output Format>
- Begin with a brief thought process detailing your approach to identifying the rank, core functional areas, and secondary keywords.

- Conclude with your final output in the form of a Python dictionary:

<predict>
{{
"rank": ["list of ranks"],
"core": ["list of core functional areas"],
"secondary": ["list of secondary functional areas"]
}}
</predict>
</Output Format>

Here is the profile data:
"""


GET_SIMILAR_COMPANIES_SYSTEM_PROMPT = """Your name is Jared and you are an expert in identifying direct competitors of companies."""

GET_SIMILAR_COMPANIES_WITH_KEYWORDS_USER_PROMPT = """
<Instructions>
- Your job is to look at products and services and the company name and give me more companies that have similar products and services.
- Do not add company name in the product or service. If the company name is present in the product or service then remove it. Like for Samsung Gear, just give Gear.
</Instructions>

<Output Format>
- First think about the problem and the give your output enclosed within in the form of a list of strings like: <predict>
1. Company Name~["Product/Service" ...]
2. Company Name~["Product/Service" ...]
3. Company Name~["Product/Service" ...]
...
</predict>
</Output Format>

<Important Instruction>
- Give the name of the respective competitor product from the competitor companies.
- Always generate at least 30 competitors, It is a bare minimum criteria.
- Strictly adhere to the described output format strictly as I will use regex to get the values from it.
- Give explicit product and service name.
</Important Instruction>
"""

GET_SIMILAR_COMPANIES_WITHOUT_KEYWORDS_USER_PROMPT = """ 
<Task>
- I'll give you a company and you have to give me it's competitors with their score according to relevancy.
</Task>

<Instruction>
- Provide a list of competitor companies with their relevancy score.
- The relevancy score should be between 1 and 10.
- Try to genrate companies of comparable size.
- Always generate at least 30 competitors, It is a bare minimum criteria.
- When generating similar companies, always consider the entity’s industry, sub-industry, and sub-sub-industry.
</Instruction>

<Important Instruction>
- Always give the company name in the output no subsidiary names. e.g. Microsoft Dynamics 365 is not a company name it should just be Microsoft.
</Important Instruction>

<Output>
- Give your thought process for every genrated company, why you think it is a competitor.
- The output should be enclosed in <output></output>.
- The output should in python dictionary format like this:
{{
"Company_Name_1": 8,
"Company_Name_2": 7,
"Company_Name_3": 6,
"Company_Name_4": 5,
.......
}}
</Output>
"""

NORMALIZE_TITLE_SYSTEM_PROMPT = """You are an intelligent assistant."""

NORMALIZE_TITLE_USER_PROMPT = f"""
<Instructions>
- You will be given a title and headline taken from a LinkedIn profile of a person. Your job is to provide more titles that can be used to find similar profiles.
- First, identify if the person holds an executive-level title or not. These titles start from Director and above.
- If the person holds an executive-level title, then just give the title in a normalized form including any acronyms.
- If the title is not executive-level, provide other similar titles as well with their scores based on relevance, scored between 1 and 10.

<Output Format>
- First, give your reasoning in detail.
- Provide the output as a Python list of strings for executive-level titles and as a dictionary for non-executive titles (values will be scores).
</Output Format>
"""

NORMALIZE_TITLE_USER_PROMPT_NEW = """
<Instruction>
    We have millions of profiles in our db. Given a person's current title and past titles, we would require all the titles that can replace the person. 
    Claude will do the following:
        1. Analyze which rank the person is currently on, and the ranks of ALL similar titles should be similar to this. We will follow the following ranking (desc order) for this task (the first element being the highest rank, the last being the lowest): ['Chiefs/Presidents/Board Members', 'Executive or Sr. VPs', 'Senior Directors', 'Directors', 'Heads', 'Managers']. You do not have to stick strictly to these but this is the heirarchy. A Chief can be replaced by another chief, or executive vp. VP can be replaced by Senior vp of another company or senior director only. You can move one up in the heirarchy or one down.
        2. Based on all the information about the person, analyze which exact business functions can be looked at to replace this person. All information will tell you about the keywords that can help you to generate all the titles required. Give as many relevant titles as you can (highest recall), but ensure that precision requirements are still met. These can be high in number. For example if "Enterprise Sales" is highly relevant, also give "Sales" with a lower score (this is essential).
        3. Against each rank and business function, assign a score again 10 for how relevant this title would be to the current title.
        4. Which are the skills that this person will likely possess. Try to get as many relevant skills as possible.
        5. Give your reasoning as well. And return the json object enclosed in <Output></Output> tags. It'll be like the following:
            Example 1:
            {
                "rank": {
                    "Manager": 10,
                    "Head": 9
                },
                "business_function": {"Enterprise Sales" : 10, "Sales" : 5, ...}, # Ensure
                "skills" : [""]
            } # We will be merging each rank with business function ourselves. You only have to give a separate list.
</Instructions>

<PersonInformation>
Current title: Senior Director of Tesla 4860
Past titles (Latest being at the top): 
    Director, Cell Manufacturing Engineering,
    Senior Manager, Cell Manufacturing Engineering,
    Senior Manager, New Product Introduction, Powertrain
    Engineering Manager
<PersonInformation>
"""

ONE_LINE_KEYWORD_SYSTEM = """<role> You are an expert in condensing information  </role>
<instructions>
- You will be given information about a person working at a company
- In one line you need to tell me what specific industry this person works in
- Make sure you capture all of the aspects of the domain
</instructions>"""

EXECUTIVE_OR_NOT_SYSTEM = """
    You are an intelligent assistant who will classify a title between three categories: ["CEO/Chairman", "Executive", "Non-Executive"]. Return the one classification in a JSON object.
"""

EXECUTIVE_OR_NOT_USER = """

    <Instructions>
        - GPT will be given a complete title of a person. You have to classify the title between ["CEO/Chairman", "Executive", "Non-Executive"].
        - Take a deep breath and understand: You will analyze whether the person is CURRENTLY a CEO or Chairman (even if he's a Chief Executive/Chair along with another role), or an Executive (Manager level or above, but NOT A CEO or a Chairman), or a Non-Executive. "Chair and CTO" is a chairman which puts it in the first case (CEO/Chairman), while "Board Member and President and Engineer" is neither a Chairman nor a CEO, but is an executive so this is the second case (Executive). Non executive roles are all below Manager level roles, such as Tech Lead, Seniors, individual contributors, etc.
    </Instructions>

    <Output_Format>
        You will return a JSON object with two keys: "classification" and "reasoning". Classification has to be between ["CEO/Chairman", "Executive", "Non-Executive"], while the "reasoning" key's value would be an explanation as to why.
    </Output_Format>

"""

MAIN_SYSTEM_PROMPT = """

"""

CEO_CHAIRMAN_USER_SYSTEM = """
<Information>
    You will be provided with the complete job title or headline of a person who is either a CEO or a Chairman. We'll be finding people similar to this person, based on this person's exact titles.
    Claude's tasks are to: 
        1. Score the titles that the person is currently holding based on relevancy. For example, if the person's job title is "Chief Executive Officer, Chair & Software engineer" then CEO, Chairman, software engineers are separate titles, but for similar profiles the term CEO should have the highest score, then a chair while Software Engineer will have a low score. If the primary title of the person was Chair then that would have the highest score. You have to see which title would be the most relevant for similar profiles. 
        2. The variations of the title MUST still MEAN the same title. For example, a "Chief" can be any chief, even those who are not CEOs, thus this does not mean the the same thing. You have to make sure the variations refer to the exact title the person holds.
        2. Your scoring will be out of 5. The primary title should have high score of 5, while the lowest should be 1. Scoring of different titles (not variations) should ideally have different scores. If two titles are equally important, the title which takes precedence in terms of day-to-day operational importance would be the primary.
        3. You will have to give all the variations of a title. For example, if a person is a CEO, "CEO", "Chief Executive Officer" and "Chief" will all be extracted. If a person is also a VP (along with being a chairman or CEO") then "VP" and "Vice President" both will be extracted with the same scores.

    Also, if the person is a chief executive, then "CEO" and "Chief Executive Officer" must be in the list, while if the person is a Chair then "Chairman" must be in the list. You will also explain all your reasoning.
</Information>
<Output_Format>
    You will return a JSON object with each title extracted as key, and the integer score as its value. Enclose this JSON object in <Output></Output> tags.
    Example:
        <Output>
            "rank": {
                "CEO" : 5 # Max score is 5,
                "Chief Executive Officer" : 5 # Variations should have the same score
                "Board Member" : 3 # If a person if "CEO and board member" then most likely people would like to see similar CEOs more than similar board members.
            }
</Output_Format>

"""

EXECUTIVE_USER_SYSTEM = """
<Instruction>
    We have millions of profiles in our db. Given a person's current title and past titles, we would require all the titles that can replace the person. These will only be logical job titles without mentioning the industry, company, etc. These have to only be based on who that person currently is.
    You will do the following:
        1. Rank Analysis and Variations: Determine the person's current rank and identify similar ranks that can be considered equivalent. Use the following hierarchy (listed from highest to lowest) as a refernce: ["Board Member", "Chief", "President", "Executive VP", "Sr. VP", 'Sr. Director', 'Director', 'Head', 'Manager'] (ranks can be different than these but follow this heirarchy). Adjustments should stay within one level up or down the hierarchy; for example, a VP could be replaced by a Senior VP or Senior Director from another company. For each rank, also give all its synonyms or variations, including abbreviations, shortened forms, etc (different ways of writing the same rank, eg. VP, Vice President; Senior, Sr.; Exec, Executive etc.).
        2. Business Function Identification: Analyze and pinpoint the primary business function of the individual based on the provided information, focusing strictly on their current role. List all related business functions and variations. For example, "Product Innovation Strategy" should also include functions like Product Strategy, Innovation, or Strategy (essential). Ensure that when analyzing business functions, broader and directly related categories such as "Analytics" are included alongside more specific ones such as "Business Analytics" to capture all relevant aspects of the role. Always give as many business functions (similar and variations) as possible, ALL of which very SIMILAR to the primary one. If no business function can be identified, give your best guesses with lower scores of business functions.
        3. Current Focus: Concentrate solely on the person's present business function. Ignore past roles or irrelevant specifics not related to their current function. For instance, if someone's background is in "electrical engineering" but they are now working in "data science," only the data science function and related areas should be considered. Use past experiences only to clarify the current business functions.
        4. Relevance Scoring: Assign a relevance score out of 10 for each rank and business function based on how closely they align with the person's current title.
        5. Which are the skills that this person will likely possess (based ONLY on the primary business function and the CURRENT title only).
        6. Give your reasoning about the current primary business function (the rest should ONLY be similar ones) as well. And return the json object enclosed in <Output></Output> tags. It'll be like the following:
            Example 1:
                <Output> 
                    {
                        "rank": {
                            "Manager": 10, # Give all exact variations of the rank with the same score
                            "Head": 9
                        },
                        "business_function": {"Enterprise Sales" : 10, "Sales" : 5, ...}, # Ensure
                        "skills" : [""]
                    } # We will be merging each rank with business function ourselves. You only have to give a separate list.
                </Output>
</Instructions>
"""

NON_EXECUTIVE_USER_SYSTEM = """
<Instruction>
    We have millions of profiles in our db. Given a person's current title and past titles (if any), we would require all the titles that can replace the person. These will only be logical job titles without mentioning the industry, company, etc.
    Claude will do the following:
        1. Based on all the information about the person, analyze which exact business functions can be looked at to replace this person. All information will tell you about the keywords that can help you to generate all the titles required. Give as many relevant titles as you can (highest recall), but ensure that precision requirements are still met. These can be high in number. For example if "Enterprise Sales" is highly relevant, also give "Sales" with a lower score (this is essential).
        3. Which are the skills that this person will likely possess. Try to get as many relevant skills as possible.
        4. Give your reasoning as well. And return the json object enclosed in <Output></Output> tags. It'll be like the following:
            Example 1:
                <Output> 
                    {
                        "rank": {
                            "Software Engineer": 10,
                            "Deep Learning Engineer": 9,
                            "AI specialist" : 8
                        },
                        "skills" : [""]
                    } # We will be merging each rank with business function ourselves. You only have to give a separate list.
                </Output>
</Instructions>
"""

BUSINESS_FUNCTION_USER_PROMPT = """
<Information>
    Claude will analyze a person's information, headline, and description to determine their primary business function and identify related functions, if they can be inferred, while also identifying whether person is an executive (manager level and above) or not.

    Claude will perform the following tasks:
        1. Primary Business Function Identification: Analyze and pinpoint the primary business function of the individual based on the provided information, if it can be inferred using the information provided. If it cannot be inferred, then return an empty list. For example, a business function can be inferred for "Director of engineering" (engineering) and also for "Director of sales of cloud" (sales), but not just a "Director". The rest of the information should only be used when necessary or when the title doesn't provide the relevant business function. You should use all the information provided to you, but the primary business function should be based on the current title given to you. For example, if someone has had other roles that can provide more insight into their specialty, use that information; however, if the primary title itself is sufficient to determine the business function, the focus should be on that."
        2. List multiple business functions that are close to the primary function (**maximum 15**). Claude must include related functions and their variations, including one word functions as well; for instance, the term "Product Innovation Strategy" encompasses "Product Strategy," "Innovation," and "Strategy" so they must be included as well. When evaluating business functions, both broad and specific categories, such as "Analytics" and "Business Analytics," should be considered to encompass all facets of the role comprehensively. Ensure that all listed business functions are similar to the primary one. If a business function cannot be distinctly identified, provide an empty list.
        3. Score each business function in relevancy to the person's CURRENT title and description.
        4. Analyze if the person is an executive (above manager level) or not. If a person is "Chief Financial Officer, Advisor", then the person would be an executive due to the CFO title.
        5. Also get multiple skills or keywords relevant to the title or the person's company (**maximum 15**). These should include specific and very broad ones as well, including one word keywords. For example, for the title "Director of engineering at Spotify", the keywords would include "music industry" but for a broader keyword search "music" would also be very effective, so "Music" should also be returned. These should ensure a very high recall.
        6. Always return a JSON object enclosed in <Output></Output> tags containing three keys. One key would be 'business_functions', which will be a json object containing the primary business function and functions similar to the primary as keys and their relevancy scores as values; another key would be 'keywords' whose value would be a list of skills/keywords that can be looked for in relevant similar profiles. It will also contain a key 'executive' whose value would be a boolean True or False.
        Example:
            <Output>
                {
                    "business_functions" : {"Human Resources" : 10, "HR" : 10, ...},
                    "keywords" : [],
                    "executive" : True # Can only be True or False
                }
            </Output>

        Take a deep breath and read the steps above twice. Explain your reasoning.
</Information> 
"""
EXECUTIVE_OR_NOT_SYSTEM_PROMPT = """
"""
SIMILAR_TITLES_USER_PROMPT = """
<Information>
    Given a person's headline and description, generate as many relevant job titles as you can (upto 10). Also include all the full forms and abbreviations of the job titles. Claude will also score each title based on relevancy to the person's headline and description.
    These job titles should be very similar to the person's domain. For example, if a person is "An AI engineer at Microsoft" then relevant job titles can be "AI Engineer", "Artificial Engineer", "DL Engineer", "Deep Learning Engineer", and so on.
    <Output_format>
        You will return a JSON object containing the titles as keys and their relevancy score as values. Must be enclosed in <Output></Output> tags.
        Example:
            <Output>
            {"AI Engineer" : 10, "Artificial Intelligence Engineer" : 10, "DL Engineer" : 8, "Deep Learning Engineer" : 8,...}
            </Output>
    </Output_format>
</Information>
"""
TITLES_SYSTEM_PROMPT = """
"""
TITLES_USER_PROMPT = """
<Information>
    We have millions of executives in our database. We can filter them out based on 4 major ranks: whether they are C-Suites, Executives (Non-C Suite to manager level), Board Members, General Managers, Presidents.
    Claude will be provided with information about a person's current headline, and business functions, and using that we are going to get people who can possibly replace this person. We want a high recall, but also good precision, so for this Claude is also going to score each title and rank it generates. Claude has to perform the following task:
    <emp>
    Analyze which ranks does the person fall in between C-Suites, Executives, Board Members. A person can even fall in multiple ranks. For each rank Claude has to analyze the relevancy score accordingly (out of 10)
    </emp>
    <Cases>
        <C-Suites>
            If the person themselves are a CSUITE executive (Must be a chief, not someone working with a chief or involved in something C-Suite related; they must hold the position of a chief themselves):
                Using the business functions provided, Claude has to return a list of CSuite titles that the person can hold, including its abbreviations and variations, and also its relevancy score. For example, if a person is a Chief Financial Officer, then {"CFO" : 10, "Chief Finance Officer" : 10} should be returned or if a person is a Chief Executive officer, CEO must be returned, and so on. If multiple business functions exist then all relevant CSUITE titles should be returned. All titles should be singular.
        <C-Suites>
        <Board>
            If the person has explicitly mentioned being a board member or a chairperson then a list will be returned containing "Board Member" and "Chair" based on what the person is. Otherwise, it will be empty.
        <Board>
        <Executive>
            If the person is also a non-CSUITE or Board executive (above director level) then Claude should return a json where the keys are ranks that the person holds, along with similar ranks, including all abbreviations and variations (variations are way of rewriting, eg. Senior, Sr. or Executive, Exec, etc.), and each one's relevancy score as value.
            For example, if a person is a "Corporate VP of Engineering" then {"Corporate VP" : 10, "Corporate Vice President" : 10, "Senior Vice President" : 8, ...} should be returned. The heirarchy we loosely follow is: Presidents, Executive VPs, Senior VPs, VPs, Senior Directors, Directors, Manager, General Manager, Managers. This is a loosely named heirarchy which should only be referenced for checking similar ranks (very close in heirarchy), but the titles themselves should be analyzed and generated by Claude. All ranks should be singular.
            These should only be included if the person holds a Non-CSuite and Non-Board level title as well, otherwise it should be empty.
        </Executive>
    </Cases>
    <Output_Format>
        Always follow the output format here. Claude will return a JSON object enclosed in <Output></Output> tags, containing 3 keys, "CSuite", "Executive", "Board". CSuite will contain all the titles (rank and business function) and their scores, Executive will contain all the non-c level ranks the person holds (and their scores) along with SIMILAR RANKS (without business functions).
        Example:
            <Output>
                {
                    "CSuite": {"CTO" : 10, "Chief Technology Officer" : 10}, # Exact titles. ONLY generate if person is in CSUITE position, otherwise should be an empty list.
                    "Board" : ["Chair"] # Can only contain "Chair", "Board Member" or be an empty list.
                    "Executive": {"VP" : 7, "Vice President" : 7, "Senior VP" : 8, "Sr VP" : 8, ......} ## ranks and variations. These would only be calculated if the person is holding a non-CSuite and non-Board position.
                }
            </Output>
    </Output_Format>
</Information>
"""

LOWER_TITLES_USER_PROMPT = """
<Information>
    We have millions of executives in our database. We can filter them out based on 4 major ranks: whether they are C-Suites, Executives (Non-C Suite to manager level), Board Members, General Managers, Presidents.
    
    Claude will be provided with information about a person's current headline, and business functions, and using that we are going to get people who can possibly replace this person. We want a high recall, but also good precision, so for this Claude is also going to score each title and rank it generates. Claude has to perform the following task:
    <emp>
    Analyze which ranks does the person fall in between C-Suites, Executives, Board Members. A person can even fall in multiple ranks. For each rank Claude has to analyze the relevancy score accordingly (out of 10)
    </emp>
    <Steps>
        <Current_Titles>
            This should be a list of titles that the person is currently holding, including abbreviations and full forms. For example, if a person if a "Chief Executive Officer, President and CTO" then ["CEO", "Chief Executive Officer", "President", "CTO", "Chief Technology Officer"] should be returned or if a person is "President of Manufacturing" then ["President of Manufacturing"] should be returned or if a person is a Senior Vice President (SVP, Senior VP) then ["Senior VP", "Senior Vice President", "SVP"] must be returned or if a person is a Exec Vice President (EVP, Executive VP) then ["Executive VP", "Executive Vice President", "EVP"] must be returned or if the person is a Corporate VP then ["CVP", "Corporate VP", "Corporate Vice President"] must be returned and so on. The titles should not include industries or company names, these are the exact job titles.
        <Board>
            If the person has explicitly mentioned being a board member or a chairperson then this will be True, otherwise False.
        <Board>
        <Executive>
            If the person is an executive (above manager level) then Claude should return a json where the keys are ranks (not titles) 2-3 levels below the person's original rank, including all abbreviations and variations (variations are way of rewriting, eg. Senior, Sr. or Executive, Exec, etc.), and each one's relevancy score as value.
            For example, if a person is a "Corporate VP of Engineering" then {"Senior Vice President" : 8, "Senior VP" : 8, ...} should be returned. The heirarchy we loosely follow is: Chiefs, Presidents, Executive VPs, Senior VPs, VPs, Senior Directors, Directors, Manager, General Manager, Managers. This is a loosely named heirarchy which should only be referenced for checking similar LOWER ranks (very close in heirarchy but lower than the person in question), but the ranks themselves should be analyzed and generated by Claude. All ranks should be singular and the relevancy score should be higher for people just below the person, and should be lower for people who are certain levels below. For example, for a CTO (who is a chief), the rank "VP" would have a level of 5 as Senior VP, Executive VPs would have higher scores. The list should only contain titles that are maximum of 2-3 ranks below the person's current ranks. The list should never contain president level or chief ranks.

            <emp>
                - Remember these will only be exact ranks LOWER THAN THE PERSON'S OWN RANK, WITHOUT any business function or company mentioned ("Sales", "Microsoft", etc. should NOT be included in ranks). 
                - Executives list should always be generated for ALL non-CEO titles.
            </emp>
        </Executive>
    </Steps>

    <Output_Format>
        Always follow the output format here. Claude will return a JSON object enclosed in <Output></Output> tags, containing 3 keys, "Current_Titles", "Executive", "Board". Current_Titles will contain all the current titles the person is holding (rank and business function) and their scores, Executive will contain all the non-c level ranks the person holds (and their scores) along with SIMILAR RANKS (without business functions), while 'Board' will contain a boolean value.
        Example:
        If the title was "Chief Human Resources Officer of Tesla and Exective VP of engineering":
            <Output>
                {
                    "current_titles": ["Chief Human Resource Officer", "CHRO", "Executive VP of Engineering", "Executive Vice President of Engineering"], # Exact current titles. # Can't include company names and industries
                    "Board" : False # Can only contain True or False
                    "Executive": {"Executive VP", "Executive Vice President", "VP" : 7, "Vice President" : 7, "Senior VP" : 8, "Sr VP" : 8, ......} ## ranks and variations. These would only be calculated if the person is holding a non-CSuite and non-Board position. Executive VP was only added here because the person is also a CHRO, which is their biggest title. Remember to only include the rank, and not the business function (if any).
                }
            </Output>
            Also provide your reasoning. Don't add comments though.
    </Output_Format>
</Information>

"""

INDUSTRY_FOR_CACHE_PROMPT = """"
<Task> 
    - Based on the given profile's data, generate a list that must include only the major product mentioned. 
    - Make sure to only generate the above one thing. The product could have more than one word. Ignore the industry. 
    - If only a company is mentioned that you don't know in the data, return an empty list. 
    - If no specific product is mentioned, also return an empty list. This is mandatory. 
    - The keyword should be the major product of the company, and no generic terms should be used if no specific product is mentioned. 
    - For the given example (Director Of Hardware Engineering, Azure at Microsoft, focusing on chip design for Azure’s cloud infrastructure), the keyword to use is "azure" (the product). 
    - Always generate a maximum one word for the product. This is mandatory, or you'll be considered to have failed in your task. All words should be in lowercase. 
</Task> 

<Output> 
    - First give your thought process  in one line.
    - Give your output in the form <prediction>["azure"]</prediction>.

    Thought Process: 
    1. Identify the product mentioned: "azure".
    3. Format in lowercase, within one word total.

    <prediction>["azure"]</prediction>
</Output>
"""
