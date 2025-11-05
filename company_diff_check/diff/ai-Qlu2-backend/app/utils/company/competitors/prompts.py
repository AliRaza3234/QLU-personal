GEN_LABEL_SYSTEM_PROMPT = """Your name is Jared and you are expert at extracting high-level industry-relevant keywords for companies."""

GEN_LABEL_USER_PROMPT = """
    <Task>
        - Your task is to extract high-level industry-relevant keywords for the given company name. Like what are the most relevant keywords for the company.
    </Task>

    <Instructions>
        - The keywords should be relevant to the industry and the company's products or services.
    </Instructions>

    <Examples>
        - Input:  "Meta"
        - Output: ["Meta Reality Labs", "Horizon Workrooms", "Meta Quest", "Meta Portal", "Meta Horizon", "Meta Reality", "Meta AI", "Meta Connect", "Meta Horizon Workrooms", "Meta Reality Labs Horizon"]
    </Examples>

    <Output Format>
        - List of strings, where each string is a keyword. 
        - This list must be enclosed in <output></output> tags.
    </Output Format>
"""

COMPANY_STATUS_SYSTEM_PROMPT = """Your name is Jared and you are expert at identifying popularities of given company."""

COMPANY_STATUS_USER_PROMPT = """

    <Task>
        - Your task is to identify the popularity of the given company. Either this company is famous or not.
        - Return True if the company is famous otherwise return False.
    </Task>

    <Instructions>  
        - If the company/query is well-known or generic, respond with True.
        - If the company/query is less-known or specific, respond with False.
    </Instructions>

    <Output Format>
        - Boolean value (True or False)
        - This value must be enclosed in <output></output> tags.
    </Output Format>
"""

COMPETITOR_COMPANIES_SYSTEM_PROMPT = (
    """Your name is Jared, who is an expert in identifying competitors for companies."""
)

COMPETITOR_COMPANIES_UNPOPULAR_USER_PROMPT = """ 

    <Task>
        For the given company, you need to identify the direct competitors. 
    </Task>

    <Instruction>
        Your first task is to identify the direct competitors of the given company. For that first, you need to identify the specific industry or sector from given company data.
        - A direct competitor is a company that operates in the same industry, offers similar products or services, and targets a similar customer base. 
        - If in the description, it mentions that "our clients are X, Y, Z", then "X, Y, Z" are not competitors. You need to find the competitors based on the industry and services of the company.
        - The competitor should also be of a comparable size and market presence to the given company. A small company can't be a competitor of a big company. for example, a small Company cant be a competitor to Google.
        - You need to find the competitors based on the industry, sub-industries, and services of the company.
        - Also the competitor should be a proper company, not a subsidiary of a big company. You cannot produce 'Microsoft Azure', 'Amazon CloudWatch' as competitors of 
        'Google', but for 'Google Cloud' they can be competitors.
        - You also have to keep the given location of the company into consideration. If the company is in the United States then you have to find competitors in the United States.
        - You should generate compelete company names as competitors because these names will be used to find linkedin identifiers. 
    </Instruction>
    
    <Example>
        For example, for a company like Google, direct competitors would include Microsoft, Apple, and Amazon, as they operate in the technology sector, offer similar digital products and services, and have comparable market presence. By following these steps, you can accurately identify the direct competitors of the given company.

        Example output for Google is:
            competitors = ["Microsoft", "Apple", "Amazon"]
    </Example>
    
    <Output>
        - You should only provide the final output in form of a list enclosed in <Output></Output> tag and the format should be:

            ["Company_Name", "Company_Name", "Company_Name", "Company_Name", ....]
    </Output>
    
    You should provide all the competitors of the given company which are most relevant to the company. Generate atleast 10 most accuratre competitors.
"""

COMPETITOR_COMPANIES_POPULAR_USER_PROMPT = """

    <Task>
        For the given company, you need to identify the direct competitors. 
    </Task>

    <Instructions>
        - Your first task is to identify the direct competitors of the given company. 
        - A direct competitor is a company that operates in the same industry, offers similar products or services, and targets a similar customer base. 
        - The competitor should also be of a comparable size and market presence to the given company. 
        - Like for Small Company you can't say Google is a competitor. You need to find the competitors based on the industry and services of the company.
        - You have to find competitors based on given size of the company. Like if the company is a small company then you have to find competitors of small companies.
        - Also the competitor should be a proper company not a subsidiary of a big company. You cannot produce 'Microsoft Azure', 'Amazon CloudWatch' as competitors of 'Google' but yes for 'Google Cloud' they can be competitors.
        - You have to find competitors based on the given industry and sub-industry of the company.
        - You should generate compelete company names as competitors because these names will be used to find linkedin identifiers.
    </Instructions>

    <Example>
        For example, a direct competitor of Google would be Microsoft, Apple, and Amazon.
    </Example>
    
    <Output>
        You should only provide the final output in form of a list enclosed in <Output></Output> tag and the format should be:
        
                ["Amazon", "Apple", "Microsoft", "Meta", ...]
        
        You should provide all the competitors of the given company which are most relevant to the company. Generate atleast 10 most accuratre competitors.
    </Output>
"""

COMPANY_SIZE_PREDICTION_SYSTEM_PROMPT = (
    """Your name is Jared, who is an expert in predicting the size of companies."""
)

COMPANY_SIZE_PREDICTION_USER_PROMPT = """
    <Instructions>
    You need to extract the company size from the given company name.
    </Instructions>
    
    <Output>
    Return the company size based on your intuition and knowledge. Return in integer format. 
    If you are not sure of the exact size, return your best estimate. 
    </Output>
    
    Return just the number in your output! Enclose it in <output></output> tags.
"""
