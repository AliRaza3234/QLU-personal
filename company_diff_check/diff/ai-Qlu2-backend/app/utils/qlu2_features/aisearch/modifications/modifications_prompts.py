DEMO_AMBIGUOUS_PROMPT_AISEARCH = """
<AI_Search>
    You will be provided with all the previous queries and their results as well, which would include details extracted from system, the texts shown to user, the modals shown to user and, importantly, the filters extracted by AI Search. Clear your ambiguities based on how the conversation is proceeding.
    We have a service called AI-Search which we use the clear prompt on when all ambiguities have been cleared: We can query our database using the following attributes:
        • "job_role": Handles job titles, management levels and the number of employees at the company where that title was held.
        • "company_industry_product": Handles Industries, Companies, Company Location, organizations, or products.
        • "skill": Specific skills or key terms.  
        • "location": Handles person location.
        • "total_working_years": Handles tenure in a company, tenure in a role and total career experience.
        • "education": Specific schools, degrees, or certifications.  
        • "name": Exact person’s name.  
        • "ownership": Include the ownership type—selecting from "Public," "Private," "VC Funded," or "Private Equity Backed" (where "Private Equity Backed" refers to an investee company, not an investor company)—only when it is explicitly mentioned in the current context. Do not infer ownership types from queries like "get people from startups" or "get people from Fortune 500," as these do not explicitly request ownership information.
        • "demographics": Handles gender, ethnicity and age.
    
    AI search can operate in two ways depending on whether the <Last_Query> is independent or dependent on previous prompts.

    1. If the <Last_Query> is **independent** and does not rely on any previously extracted filters, a fresh AI search will be run. In this case:
        - The system should extract new filters from the clear_prompt.
        - The "action" variable should be set to "extract".

    2. If the <Last_Query> is **dependent** on previous results (i.e., the user wants to update filters from a previous AI search), then:
        - The clear_prompt will be treated as an instruction describing how the previous filters should be modified (e.g., "Change location to USA", "Remove skills", "Add age 50+ and location Europe").
        - **The clear prompt should be a direct and straight-forward instruction**: "Add this", "Change this", etc.**
        - The system should identify:
            - Which attributes need to be modified. # Ensure you look at all the attributes which have extracted previously and decide carefully which require changes.
            - Which result indexes (from the previous AI search results) are affected by these modifications.
        - The "action" variable should be set to "modify".
        - The "indexes" key will contain the relevant result indexes.
</AI_Search>
<Timeline>
    We have four distinct timelines/events for all filters: Current, Past, Current and Past, and Current or Past. When the user requests a profile that has worked in a role, company, location, or industry—regardless of when (using terms like experience, worked at, background of, etc.)—then OR is applied to that specific filter’s timeline. If the user specifies that someone used to work in one thing and currently works in another, then AND is applied to that specific filter only.

    The way filters are linked is as follows: when the user asks for people who are currently in a role at a company or were in that exact same role at that same company before, then using AND in both job titles/levels and companies (this is incorrect for this example) will return only those profiles who are currently in that role at that company and were previously in that same role at that same company. However, if OR is used in both roles and companies (which is correct for this example), it will return profiles who are currently in that role at that company or were previously in that role at that company.

    If titles are marked as Current and companies as Past, then profiles will be returned of people who have that current role and used to work in that company before (regardless of what role they had in that company). If titles are marked as Current and Past (which means titles are clearly marked to be current or past or both) and companies as Current, then profiles will be returned of people who currently have the current roles in that company and had the past roles in any company in the past (whether the same company or a different one). The same logic applies in reverse—when companies are marked as AND and titles as Current.

    So, if job role or companies/industries are being modified, then ensure that the timeline is correctly applied to all the required filters and explain this in the output as well. For example, if the user asked for people who are/were VPs of Google then companies and titles both would be applied in OR. If the user now wants only those who are currently working as VPs at Google, then timeline of BOTH would need to be changed to CURRENT. Remember, when users are okay with whether somebody has worked in a role before or is working in a role then 'CURRENT OR PAST' is applied and the same for the rest of the filters. Explain if you keep the companies timeline as it is and change the job role, would that satisfy what the user requires? For example, if the user asked for people who are CEOs of Google and then they also want people were CEOs of Google before then CEOs would be changed to Current or past and so would Google as that is only in current right now.
</Timeline>
<Output_format>
    - First write your entire reasoning and chain of thought, inside `<reasoning>` `</reasoning>` tags. Analyze the entire conversation and see the `<Last_Query>` in relation to the entire previous context.
    - Return a JSON object enclosed in <Output> </Output> tags.
    - Include a "clear_prompt" key with a clearly rewritten version of the query or a filter modification instruction.
    - Include an "action" key with value "extract" or "modify". Read the previous prompts in the previous conversation to see whether the user is modifying older query or is it a newer query.
    - If action = "extract":
        - AI search will run as it will be a new search with no connection to any of the previous AI search; all filters to be extracted based on the clear prompt.
    - If action = "modify":
        - Include a "attributes" key which will be a list of the attributes that require modification and to whom the clear prompt would be sent to. You have to be smart about such changes, for example if somebody asked that candidates for CFO for a large tech company are also added to the original list, this will be a modification and then "Change to CFO candidates from large tech companies" would be the clear_prompt, while filters would include job_role and company_industry_product. You will have to see the previous AI search results to know what changes would make sense.
        - Attributes to modify MUST only contain from the following list: ["skill", "location", "job_role", "company_industry_product", "total_working_years", "education", "name", "ownership", "demographics"]. These are the names of the agents which handle their specific filters so attributes must only contain one of these and NONE OTHER. For example, if the user mentions management level then job_role will be called. Analyze which attributes need to be called (if the user specifies a location generally, it's probably referring to people's location. But if they EXPLICITLY clarify that they refered to it as the company's location, then company_industry_product should be called)
        - Include an "indexes" key with the indexes of results to which the modifications should apply (the last index's results MUST CONTAIN the "AI_Search_Results" which require modification). Explain how you chose the values inside the indexes key and whether the results of that index (Result-0 for example actually contained AI_Search_Results.)

    If the step is extract:
        {
            "clear_prompt": "",
            "action": "extract",
        }
    
    If the step is modify:
        {
            "clear_prompt": "",
            "action": "modify",
            "attributes": [""], # Can only contain values from the list ["skill", "location", "job_role", "company_industry_product", "total_working_years", "education", "name", "ownership", "demographics"]. 
            "indexes": [0,1], # last index must contain the AI_SEARCH_RESULTS to modify
        }

    Provide your reasoning and then give your output
</Output_format>
"""

# 3 Changes
DEMO_AMBIGUOUS_PROMPT_AISEARCH_INDUSTRY = """
<AI_Search>
    You will be provided with all the previous queries and their results as well, which would include details extracted from system, the texts shown to user, the modals shown to user and, importantly, the filters extracted by AI Search. Clear your ambiguities based on how the conversation is proceeding.
    We have a service called AI-Search which we use the clear prompt on when all ambiguities have been cleared: We can query our database using the following attributes:
        • "job_role": Handles job titles, management levels and the number of employees at the company where that title was held.
        • "company_product": Handles Companies, Company Location, organizations, or products
        • "industry": Handles the industry keyword filter. You have to see what the user requires and change the industry or the company_product label according to the user's demand.
        • "skill": Specific skills or key terms.  
        • "location": Handles person location.
        • "total_working_years": Handles tenure in a company, tenure in a role and total career experience.
        • "education": Specific schools, degrees, or certifications.  
        • "name": Exact person’s name.  
        • "ownership": Include the ownership type—selecting from "Public," "Private," "VC Funded," or "Private Equity Backed" (where "Private Equity Backed" refers to an investee company, not an investor company)—only when it is explicitly mentioned in the current context. Do not infer ownership types from queries like "get people from startups" or "get people from Fortune 500," as these do not explicitly request ownership information.
        • "demographics": Handles gender, ethnicity and age.
    
    AI search can operate in two ways depending on whether the <Last_Query> is independent or dependent on previous prompts.

    1. If the <Last_Query> is **independent** and does not rely on any previously extracted filters, a fresh AI search will be run. In this case:
        - The system should extract new filters from the clear_prompt.
        - The "action" variable should be set to "extract".

    2. If the <Last_Query> is **dependent** on previous results (i.e., the user wants to update filters from a previous AI search), then:
        - The clear_prompt will be treated as an instruction describing how the previous filters should be modified (e.g., "Change location to USA", "Remove skills", "Add age 50+ and location Europe").
        - **The clear prompt should be a direct and straight-forward instruction**: "Add this", "Change this", etc.**
        - The system should identify:
            - Which attributes need to be modified. # Ensure you look at all the attributes which have extracted previously and decide carefully which require changes.
            - Which result indexes (from the previous AI search results) are affected by these modifications.
        - The "action" variable should be set to "modify".
        - The "indexes" key will contain the relevant result indexes.
</AI_Search>
<Timeline>
    We have four distinct timelines/events for all filters: Current, Past, Current and Past, and Current or Past. When the user requests a profile that has worked in a role, company, location, or industry—regardless of when (using terms like experience, worked at, background of, etc.)—then OR is applied to that specific filter’s timeline. If the user specifies that someone used to work in one thing and currently works in another, then AND is applied to that specific filter only.

    The way filters are linked is as follows: when the user asks for people who are currently in a role at a company or were in that exact same role at that same company before, then using AND in both job titles/levels and companies (this is incorrect for this example) will return only those profiles who are currently in that role at that company and were previously in that same role at that same company. However, if OR is used in both roles and companies (which is correct for this example), it will return profiles who are currently in that role at that company or were previously in that role at that company.

    If titles are marked as Current and companies as Past, then profiles will be returned of people who have that current role and used to work in that company before (regardless of what role they had in that company). If titles are marked as Current and Past (which means titles are clearly marked to be current or past or both) and companies as Current, then profiles will be returned of people who currently have the current roles in that company and had the past roles in any company in the past (whether the same company or a different one). The same logic applies in reverse—when companies are marked as AND and titles as Current.

    So, if job role or companies/industries are being modified, then ensure that the timeline is correctly applied to all the required filters and explain this in the output as well. For example, if the user asked for people who are/were VPs of Google then companies and titles both would be applied in OR. If the user now wants only those who are currently working as VPs at Google, then timeline of BOTH would need to be changed to CURRENT. Remember, when users are okay with whether somebody has worked in a role before or is working in a role then 'CURRENT OR PAST' is applied and the same for the rest of the filters. Explain if you keep the companies timeline as it is and change the job role, would that satisfy what the user requires? For example, if the user asked for people who are CEOs of Google and then they also want people were CEOs of Google before then CEOs would be changed to Current or past and so would Google as that is only in current right now.
</Timeline>
<Output_format>
    - First write your entire reasoning and chain of thought, inside `<reasoning>` `</reasoning>` tags. Analyze the entire conversation and see the `<Last_Query>` in relation to the entire previous context.
    - Return a JSON object enclosed in <Output> </Output> tags.
    - Include a "clear_prompt" key with a clearly rewritten version of the query or a filter modification instruction.
    - Include an "action" key with value "extract" or "modify". Read the previous prompts in the previous conversation to see whether the user is modifying older query or is it a newer query.
    - If action = "extract":
        - AI search will run as it will be a new search with no connection to any of the previous AI search; all filters to be extracted based on the clear prompt.
    - If action = "modify":
        - Include a "attributes" key which will be a list of the attributes that require modification and to whom the clear prompt would be sent to. You have to be smart about such changes, for example if somebody asked that candidates for CFO for a large tech company are also added to the original list, this will be a modification and then "Change to CFO candidates from large tech companies" would be the clear_prompt, while filters would include job_role and company_product. You will have to see the previous AI search results to know what changes would make sense.
        - Attributes to modify MUST only contain from the following list: ["skill", "location", "job_role", "company_product", "industry", "total_working_years", "education", "name", "ownership", "demographics"]. These are the names of the agents which handle their specific filters so attributes must only contain one of these and NONE OTHER. For example, if the user mentions management level then job_role will be called. Analyze which attributes need to be called (if the user specifies a location generally, it's probably referring to people's location. But if they EXPLICITLY clarify that they refered to it as the company's location, then company_product should be called)
        - Include an "indexes" key with the indexes of results to which the modifications should apply (the last index's results MUST CONTAIN the "AI_Search_Results" which require modification). Explain how you chose the values inside the indexes key and whether the results of that index (Result-0 for example actually contained AI_Search_Results.)

    If the step is extract:
        {
            "clear_prompt": "",
            "action": "extract",
        }
    
    If the step is modify:
        {
            "clear_prompt": "",
            "action": "modify",
            "attributes": [""], # Can only contain values from the list ["skill", "location", "job_role", "company_product", "industry", "total_working_years", "education", "name", "ownership", "demographics"]. 
            "indexes": [0,1], # last index must contain the AI_SEARCH_RESULTS to modify
        }

    Provide your reasoning and then give your output
</Output_format>
"""


NO_DEMO_AMBIGUOUS_PROMPT_AISEARCH = """
<AI_Search>
    You will be provided with all the previous queries and their results as well, which would include details extracted from system, the texts shown to user, the modals shown to user and, importantly, the filters extracted by AI Search. Clear your ambiguities based on how the conversation is proceeding.
    We have a service called AI-Search which we use the clear prompt on when all ambiguities have been cleared: We can query our database using the following attributes:
        • "job_role": Handles job titles, management levels and the number of employees at the company where that title was held.
        • "company_industry_product": Handles Industries, Companies, Company Location, organizations, or products.
        • "skill": Specific skills or key terms.  
        • "location": Handles person location.
        • "total_working_years": Handles tenure in a company, tenure in a role and total career experience.
        • "education": Specific schools, degrees, or certifications.  
        • "name": Exact person’s name.  
        • "ownership": Include the ownership type—selecting from "Public," "Private," "VC Funded," or "Private Equity Backed" (where "Private Equity Backed" refers to an investee company, not an investor company)—only when it is explicitly mentioned in the current context. Do not infer ownership types from queries like "get people from startups" or "get people from Fortune 500," as these do not explicitly request ownership information.
        We do not handle demographics, age, ethnicity, gender or anything.
    
    AI search can operate in two ways depending on whether the <Last_Query> is independent or dependent on previous prompts.

    1. If the <Last_Query> is **independent** and does not rely on any previously extracted filters, a fresh AI search will be run. In this case:
        - The system should extract new filters from the clear_prompt.
        - The "action" variable should be set to "extract".

    2. If the <Last_Query> is **dependent** on previous results (i.e., the user wants to update filters from a previous AI search), then:
        - The clear_prompt will be treated as an instruction describing how the previous filters should be modified (e.g., "Change location to USA", "Remove skills", "Add age 50+ and location Europe").
        - **The clear prompt should be a direct and straight-forward instruction**: "Add this", "Change this", etc.**
        - The system should identify:
            - Which attributes need to be modified. # Ensure you look at all the attributes which have extracted previously and decide carefully which require changes.
            - Which result indexes (from the previous AI search results) are affected by these modifications.
        - The "action" variable should be set to "modify".
        - The "indexes" key will contain the relevant result indexes.

</AI_Search>
<Timeline>
    We have four distinct timelines/events for all filters: Current, Past, Current and Past, and Current or Past. When the user requests a profile that has worked in a role, company, location, or industry—regardless of when (using terms like experience, worked at, background of, etc.)—then OR is applied to that specific filter’s timeline. If the user specifies that someone used to work in one thing and currently works in another, then AND is applied to that specific filter only.

    The way filters are linked is as follows: when the user asks for people who are currently in a role at a company or were in that exact same role at that same company before, then using AND in both job titles/levels and companies (this is incorrect for this example) will return only those profiles who are currently in that role at that company and were previously in that same role at that same company. However, if OR is used in both roles and companies (which is correct for this example), it will return profiles who are currently in that role at that company or were previously in that role at that company.

    If titles are marked as Current and companies as Past, then profiles will be returned of people who have that current role and used to work in that company before (regardless of what role they had in that company). If titles are marked as Current and Past (which means titles are clearly marked to be current or past or both) and companies as Current, then profiles will be returned of people who currently have the current roles in that company and had the past roles in any company in the past (whether the same company or a different one). The same logic applies in reverse—when companies are marked as AND and titles as Current.

    So, if job role or companies/industries are being modified, then ensure that the timeline is correctly applied to all the required filters and explain this in the output as well. For example, if the user asked for people who are/were VPs of Google then companies and titles both would be applied in OR. If the user now wants only those who are currently working as VPs at Google, then timeline of BOTH would need to be changed to CURRENT. Remember, when users are okay with whether somebody has worked in a role before or is working in a role then 'CURRENT OR PAST' is applied and the same for the rest of the filters. Explain if you keep the companies timeline as it is and change the job role, would that satisfy what the user requires? For example, if the user asked for people who are CEOs of Google and then they also want people were CEOs of Google before then CEOs would be changed to Current or past and so would Google as that is only in current right now.
</Timeline>
<Output_format>
    - First write your entire reasoning and chain of thought, inside `<reasoning>` `</reasoning>` tags. Analyze the entire conversation and see the `<Last_Query>` in relation to the entire previous context.
    - Return a JSON object enclosed in <Output> </Output> tags.
    - Include a "clear_prompt" key with a clearly rewritten version of the query or a filter modification instruction.
    - Include an "action" key with value "extract" or "modify". Read the previous prompts in the previous conversation to see whether the user is modifying older query or is it a newer query.
    - If action = "extract":
        - AI search will run as it will be a new search with no connection to any of the previous AI search; all filters to be extracted based on the clear prompt.
    - If action = "modify":
        - Include a "attributes" key which will be a list of the attributes that require modification and to whom the clear prompt would be sent to. You have to be smart about such changes, for example if somebody asked that candidates for CFO for a large tech company are also added to the original list, this will be a modification and then "Change to CFO candidates from large tech companies" would be the clear_prompt, while filters would include job_role and company_industry_product. You will have to see the previous AI search results to know what changes would make sense.
        - Attributes to modify MUST only contain from the following list: ["skill", "location", "job_role", "company_industry_product", "total_working_years", "education", "name", "ownership"]. These are the names of the agents which handle their specific filters so attributes must only contain one of these and NONE OTHER. For example, if the user mentions management level then job_role will be called. Analyze which attributes need to be called (if the user specifies a location generally, it's probably referring to people's location. But if they EXPLICITLY clarify that they refered to it as the company's location, then company_industry_product should be called)
        - Include an "indexes" key with the indexes of results to which the modifications should apply (the last index's results MUST CONTAIN the "AI_Search_Results" which require modification). Explain how you chose the values inside the indexes key and whether the results of that index (Result-0 for example actually contained AI_Search_Results.)

    If the step is extract:
        {
            "clear_prompt": "",
            "action": "extract",
        }
    
    If the step is modify:
        {
            "clear_prompt": "",
            "action": "modify",
            "attributes": [""], # Can only contain values from the list ["skill", "location", "job_role", "company_industry_product", "total_working_years", "education", "name", "ownership"]. 
            "indexes": [0,1], # last index must contain the AI_SEARCH_RESULTS to modify
        }

    Provide your reasoning and then give your output
</Output_format>
"""

# 3 Changes
NO_DEMO_AMBIGUOUS_PROMPT_AISEARCH_INDUSTRY = """
<AI_Search>
    You will be provided with all the previous queries and their results as well, which would include details extracted from system, the texts shown to user, the modals shown to user and, importantly, the filters extracted by AI Search. Clear your ambiguities based on how the conversation is proceeding.
    We have a service called AI-Search which we use the clear prompt on when all ambiguities have been cleared: We can query our database using the following attributes:
        • "job_role": Handles job titles, management levels and the number of employees at the company where that title was held.
        • "company_product": Handles Companies, Company Location, organizations, or products
        • "industry": Handles the industry keyword filter. You have to see what the user requires and change the industry or the company_product label according to the user's demand.
        • "skill": Specific skills or key terms.  
        • "location": Handles person location.
        • "total_working_years": Handles tenure in a company, tenure in a role and total career experience.
        • "education": Specific schools, degrees, or certifications.  
        • "name": Exact person’s name.  
        • "ownership": Include the ownership type—selecting from "Public," "Private," "VC Funded," or "Private Equity Backed" (where "Private Equity Backed" refers to an investee company, not an investor company)—only when it is explicitly mentioned in the current context. Do not infer ownership types from queries like "get people from startups" or "get people from Fortune 500," as these do not explicitly request ownership information.
        We do not handle demographics, age, ethnicity, gender or anything.
    
    AI search can operate in two ways depending on whether the <Last_Query> is independent or dependent on previous prompts.

    1. If the <Last_Query> is **independent** and does not rely on any previously extracted filters, a fresh AI search will be run. In this case:
        - The system should extract new filters from the clear_prompt.
        - The "action" variable should be set to "extract".

    2. If the <Last_Query> is **dependent** on previous results (i.e., the user wants to update filters from a previous AI search), then:
        - The clear_prompt will be treated as an instruction describing how the previous filters should be modified (e.g., "Change location to USA", "Remove skills", "Add age 50+ and location Europe").
        - **The clear prompt should be a direct and straight-forward instruction**: "Add this", "Change this", etc.**
        - The system should identify:
            - Which attributes need to be modified. # Ensure you look at all the attributes which have extracted previously and decide carefully which require changes.
            - Which result indexes (from the previous AI search results) are affected by these modifications.
        - The "action" variable should be set to "modify".
        - The "indexes" key will contain the relevant result indexes.
</AI_Search>
<Timeline>
    We have four distinct timelines/events for all filters: Current, Past, Current and Past, and Current or Past. When the user requests a profile that has worked in a role, company, location, or industry—regardless of when (using terms like experience, worked at, background of, etc.)—then OR is applied to that specific filter’s timeline. If the user specifies that someone used to work in one thing and currently works in another, then AND is applied to that specific filter only.

    The way filters are linked is as follows: when the user asks for people who are currently in a role at a company or were in that exact same role at that same company before, then using AND in both job titles/levels and companies (this is incorrect for this example) will return only those profiles who are currently in that role at that company and were previously in that same role at that same company. However, if OR is used in both roles and companies (which is correct for this example), it will return profiles who are currently in that role at that company or were previously in that role at that company.

    If titles are marked as Current and companies as Past, then profiles will be returned of people who have that current role and used to work in that company before (regardless of what role they had in that company). If titles are marked as Current and Past (which means titles are clearly marked to be current or past or both) and companies as Current, then profiles will be returned of people who currently have the current roles in that company and had the past roles in any company in the past (whether the same company or a different one). The same logic applies in reverse—when companies are marked as AND and titles as Current.

    So, if job role or companies/industries are being modified, then ensure that the timeline is correctly applied to all the required filters and explain this in the output as well. For example, if the user asked for people who are/were VPs of Google then companies and titles both would be applied in OR. If the user now wants only those who are currently working as VPs at Google, then timeline of BOTH would need to be changed to CURRENT. Remember, when users are okay with whether somebody has worked in a role before or is working in a role then 'CURRENT OR PAST' is applied and the same for the rest of the filters. Explain if you keep the companies timeline as it is and change the job role, would that satisfy what the user requires? For example, if the user asked for people who are CEOs of Google and then they also want people were CEOs of Google before then CEOs would be changed to Current or past and so would Google as that is only in current right now.
</Timeline>
<Output_format>
    - First write your entire reasoning and chain of thought, inside `<reasoning>` `</reasoning>` tags. Analyze the entire conversation and see the `<Last_Query>` in relation to the entire previous context.
    - Return a JSON object enclosed in <Output> </Output> tags.
    - Include a "clear_prompt" key with a clearly rewritten version of the query or a filter modification instruction.
    - Include an "action" key with value "extract" or "modify". Read the previous prompts in the previous conversation to see whether the user is modifying older query or is it a newer query.
    - If action = "extract":
        - AI search will run as it will be a new search with no connection to any of the previous AI search; all filters to be extracted based on the clear prompt.
    - If action = "modify":
        - Include a "attributes" key which will be a list of the attributes that require modification and to whom the clear prompt would be sent to. You have to be smart about such changes, for example if somebody asked that candidates for CFO for a large tech company are also added to the original list, this will be a modification and then "Change to CFO candidates from large tech companies" would be the clear_prompt, while filters would include job_role and company_product. You will have to see the previous AI search results to know what changes would make sense.
        - Attributes to modify MUST only contain from the following list: ["skill", "location", "job_role", "company_product", "industry", "total_working_years", "education", "name", "ownership"]. These are the names of the agents which handle their specific filters so attributes must only contain one of these and NONE OTHER. For example, if the user mentions management level then job_role will be called. Analyze which attributes need to be called (if the user specifies a location generally, it's probably referring to people's location. But if they EXPLICITLY clarify that they refered to it as the company's location, then company_product should be called)
        - Include an "indexes" key with the indexes of results to which the modifications should apply (the last index's results MUST CONTAIN the "AI_Search_Results" which require modification). Explain how you chose the values inside the indexes key and whether the results of that index (Result-0 for example actually contained AI_Search_Results.)

    If the step is extract:
        {
            "clear_prompt": "",
            "action": "extract",
        }
    
    If the step is modify:
        {
            "clear_prompt": "",
            "action": "modify",
            "attributes": [""], # Can only contain values from the list ["skill", "location", "job_role", "company_industry_product", "industry", "total_working_years", "education", "name", "ownership"]. 
            "indexes": [0,1], # last index must contain the AI_SEARCH_RESULTS to modify
        }

    Provide your reasoning and then give your output
</Output_format>
"""
