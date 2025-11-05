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

FUNCTION_KEYWORDS_SYSTEM_PROMPT = """
    You are an intelligent assistant named Jared.
"""

FUNCTION_KEYWORDS_USER_PROMPT = """
    <Instructions>
        - Given a person's LinkedIn profile data, extract the following:
            - **Rank**: Identify the rank or position level from the title. For example, in "Director of Engineering," the rank is "Director."
            - **Core Functional Areas**: Extract keywords that are most commonly used in job titles, such as "Engineering" or "Technology." These will be used for strict substring matching in titles.
            - **Secondary Functional Areas**: Extract additional keywords or industry-specific terms that can help in loosely matching and better sorting of profiles. Examples include "BFSI," "Banking," or "Finance."

        - Ensure that core functions are terms frequently found in job titles and represent primary domains of work or specialization.

        - If the title or headline contains multiple functional areas or keywords, list each separately, ensuring they represent distinct departments or specializations.

        - If the keywords are not explicitly mentioned in the title or headline, do not infer them.

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
    - Give your thought process for every genrated company, why you think it is a competitor.
    - First think about the problem and the give your output enclosed within in the form of a list of strings like: <predict>
        1. Company Name~["Product/Service" ...]
        2. Company Name~["Product/Service" ...]
        3. Company Name~["Product/Service" ...]
    ...
    </predict>
    </Output Format>

    <Important Instruction>
    - Give the name of the respective competitor product from the competitor companies.
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
        - Always generate atleast 20 competitors.
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

NORMALIZE_TITLE_SYSTEM_PROMPT = """You are an intelligent assistant whose job is to provide me with more titles that are relevant to the one provided to you."""

NORMALIZE_TITLE_USER_PROMPT = """          
    <Instructions>
        - Generate different variations of the title by creating slight modifications that retain the same core meaning without altering the position’s intended level or scope.

        - Normalize the title to its core meaning, focusing on the most critical term (often positional or hierarchical) and retain only essential descriptors that clarify rank, scale, or scope (e.g., "Global Head," "Senior Manager"). Avoid using overly specific department or function names if they are not essential to defining the level of authority.

        - Keep the most generalized term. For example, in "Head of Hardware Engineering," the title can be simplified to "Head" to capture the rank only without narrowing it to a sub-department.

        - Avoid reducing titles to overly generic forms. For instance, "Associate Head" should retain its prefix rather than simplifying to just "Head," since "Associate" reflects a specific rank within the hierarchy.

        - Use acronyms only if they are widely recognized in the industry. Do not create abbreviations.

        - Incase of specific titles like "Advisors" or "Consultants" you have to generate only specific titles like if "Technical Advisor" is given then generate "Technical Advisor" only.

        - If you get a C-Suite Level title then do not drill it so much, Because these titles will be used for sub-string matching in Elasticsearch, if you do so we will get the irrelevant results.

        - For titles containing multiple roles, break them down into individual titles. For example, "CEO and President" should be split into ["CEO", "President", "Chief Executive Officer"]. If the title is like Co-CEO then split it into ["Co-CEO", "CEO"].
    </Instructions>

    <Examples>
        - For "VP of Engineering at Microsoft Azure Services," the response should be ["VP", "Vice President"].

        - For "Software Engineer," the response should be ["Software Engineer", "Software Developer", "SWE"].

        - For "Global Head of CEO Practice," the response should be ["Global Head"].

        - For "Associate Head of Hardware Engineering," the response should be ["Associate Head", "Deputy Head", "Assistant Head"].
    </Examples>

    <Output Format>
        - Start with a detailed thought process that explains each decision made based on the instructions.
        - Provide your final output as a list enclosed within <predict></predict>.
    </Output Format>
"""

SIMILAR_REIGOINS_SYSTEM_PROMPT = """You are Jared who's an expert in generating similar countries based on given country."""

SIMILAR_REIGOINS_USER_PROMPT = """
    <Instructions>
        - For the given country, generate a list of countries where the company has important offices or branches, prioritizing these locations. The input country must be the first item in the list.
    </Instructions>

    <Hirearchy>
        Given Hirarchy of countries:
                "Northern Europe": [
                    "Denmark",
                    "Sweden",
                    "Norway",
                    "Finland",
                    "Iceland"
                ],
                "Western Europe": [
                    "France",
                    "Germany",
                    "Netherlands",
                    "Belgium",
                    "Luxembourg",
                    "Austria",
                    "Switzerland"
                ],
                "Southern Europe": [
                    "Italy",
                    "Spain",
                    "Portugal",
                    "Greece",
                    "Malta",
                    "Cyprus"
                ],
                "Eastern Europe": [
                    "Poland",
                    "Czech Republic",
                    "Hungary",
                    "Ukraine",
                    "Belarus",
                    "Slovakia",
                    "Bulgaria",
                    "Romania",
                    "Serbia",
                    "Croatia",
                    "Bosnia and Herzegovina",
                    "North Macedonia",
                    "Montenegro",
                    "Albania",
                    "Moldova"
                ],
                "Baltic States": [
                    "Estonia",
                    "Latvia",
                    "Lithuania"
                ],
                "Benelux": [
                    "Belgium",
                    "Netherlands",
                    "Luxembourg"
                ],
                "British Isles": [
                    "United Kingdom",
                    "Scotland",
                    "Wales",
                    "Ireland"
                ],
                "Balkans": [
                    "Croatia",
                    "Serbia",
                    "Bosnia and Herzegovina",
                    "North Macedonia",
                    "Montenegro",
                    "Albania",
                    "Kosovo"
                ],
                "Central Africa": [
                    "Cameroon",
                    "Central African Republic",
                    "Chad",
                    "Equatorial Guinea",
                    "Gabon",
                    "Republic of the Congo",
                    "Democratic Republic of the Congo"
                ],
                "East Africa": [
                    "Kenya",
                    "Tanzania",
                    "Uganda",
                    "Rwanda",
                    "Burundi",
                    "Ethiopia",
                    "Somalia",
                    "South Sudan",
                    "Eritrea"
                ],
                "West Africa": [
                    "Nigeria",
                    "Ghana",
                    "Côte d'Ivoire",
                    "Senegal",
                    "Liberia",
                    "Sierra Leone",
                    "Benin",
                    "Togo",
                    "Burkina Faso",
                    "Gambia",
                    "Guinea",
                    "Guinea-Bissau",
                    "Cape Verde",
                    "São Tomé and Principe"
                ],
                "North Africa": [
                    "Egypt",
                    "Morocco",
                    "Algeria",
                    "Tunisia",
                    "Libya",
                    "Sudan",
                    "Mauritania",
                    "Western Sahara"
                ],
                "Southern Africa": [
                    "South Africa",
                    "Namibia",
                    "Botswana",
                    "Zimbabwe",
                    "Zambia",
                    "Mozambique",
                    "Malawi",
                    "Lesotho",
                    "Eswatini",
                    "Angola",
                    "Madagascar",
                    "Mauritius",
                    "Seychelles",
                    "Comoros"
                ],
                "Middle East": [
                    "Saudi Arabia",
                    "Iran",
                    "Iraq",
                    "Syria",
                    "Jordan",
                    "Lebanon",
                    "Palestine",
                    "Yemen"
                ],
                "Gulf States": [
                    "United Arab Emirates",
                    "Qatar",
                    "Kuwait",
                    "Bahrain",
                    "Oman",
                    "Saudi Arabia"
                ],
                "South Asia": [
                    "Pakistan",
                    "Bangladesh",
                    "Nepal",
                    "Sri Lanka",
                    "Bhutan",
                    "Maldives"
                ],
                "Southeast Asia": [
                    "Thailand",
                    "Vietnam",
                    "Indonesia",
                    "Malaysia",
                    "Philippines",
                    "Singapore",
                    "Myanmar",
                    "Cambodia",
                    "Laos",
                    "Brunei",
                    "Timor-Leste"
                ],
                "East Asia": [
                    "China",
                    "Japan",
                    "South Korea",
                    "North Korea",
                    "Mongolia",
                    "Taiwan"
                ],
                "Central Asia": [
                    "Kazakhstan",
                    "Uzbekistan",
                    "Turkmenistan",
                    "Kyrgyzstan",
                    "Tajikistan"
                ],
                "Australasia": [
                    "Australia",
                    "New Zealand"
                ],
                "Pacific Islands": [
                    "Fiji",
                    "Samoa",
                    "Tonga",
                    "Palau",
                    "Marshall Islands",
                    "Micronesia",
                    "Nauru",
                    "Tuvalu",
                    "Vanuatu"
                ],
                "Caribbean": [
                    "Cuba",
                    "Jamaica",
                    "Bahamas",
                    "Barbados",
                    "Trinidad and Tobago",
                    "Dominican Republic",
                    "Haiti",
                    "Grenada",
                    "Saint Kitts and Nevis",
                    "Saint Lucia",
                    "Saint Vincent and the Grenadines",
                    "Dominica",
                    "Antigua and Barbuda",
                    "Belize",
                    "Costa Rica",
                    "El Salvador",
                    "Guatemala",
                    "Honduras",
                    "Nicaragua",
                    "Panama"
                ],
                "Central America": [
                    "Belize",
                    "Costa Rica",
                    "El Salvador",
                    "Guatemala",
                    "Honduras",
                    "Nicaragua",
                    "Panama"
                ],
                "North America": [
                    "Canada",
                    "Mexico"
                ],
                "South America": [
                    "Brazil",
                    "Argentina",
                    "Chile",
                    "Colombia",
                    "Peru",
                    "Venezuela",
                    "Ecuador",
                    "Bolivia",
                    "Paraguay",
                    "Uruguay",
                    "Guyana",
                    "Suriname"
                ],
                "CIS Countries": [
                    "Ukraine",
                    "Belarus",
                    "Kazakhstan",
                    "Armenia",
                    "Azerbaijan",
                    "Georgia",
                    "Uzbekistan",
                    "Turkmenistan",
                    "Kyrgyzstan",
                    "Tajikistan",
                    "Moldova"
                ],
                "Iberian Peninsula": [
                    "Spain",
                    "Portugal",
                    "Andorra",
                    "Gibraltar"
                ],
                "Mediterranean": [
                    "Italy",
                    "Spain",
                    "France",
                    "Greece",
                    "Turkey",
                    "Egypt",
                    "Israel",
                    "Lebanon",
                    "Syria",
                    "Morocco",
                    "Algeria",
                    "Tunisia",
                    "Libya",
                    "Malta",
                    "Cyprus"
                ],
                "India": ["India"],
                "United States": ["United States"],
                "Russia": ["Russia"],
                "Israel": ["Israel"]
    </Hirearchy>

    </Guidelines>
        - Given above for the input country, you will give the similar countries from above list. And the input country should be at the first index in the list. Like if the input country is "India" then the output should be ["India"] because you can only use above list to generate similar countries.
        - You can only infer your own thoughts to if you think some country is missing from the list.
    </Guidelines>

    <Format> 
        - Then, provide python list enclosed in: <output></output>
    </Format>
"""

VALIDATOR_AGENT_SYSTEM_PROMPT = (
    """You are Jared who's an expert in ranking people based on their titles."""
)

VALIDATOR_AGENT_USER_PROMPT = """
    <Instructions>
        - For the given job title, assign it a rank from 1 to 20.
    </Instructions>

    <Reference>
        - Use this hierarchy to find the closest rank:
            1: Intern
            2: Trainee
            3: Junior Assistant
            4: Assistant
            5: Junior Associate
            6: Associate
            7: Senior Associate
            8: Analyst
            9: Senior Analyst
            10: Consultant
            11: Senior Consultant
            12: Manager
            13: Senior Manager
            14: Director
            15: Senior Director
            16: Vice President
            17: Senior Vice President
            18: Executive Vice President
            19: Chief Officer (e.g., CFO, COO, CTO)
            20: Chief Executive Officer (CEO)
    </Reference>

    <Guidelines>
        - Focus on the actual responsibilities and level of authority of the position.
        - Do not assign a higher rank solely because the role supports or reports to high-ranking executives.
        - "Assistant" roles generally correspond to rank 4 (Assistant), even if they are "Executive Assistants" to top executives.
        - Consider the job functions rather than the job title's proximity to executives.
    </Guidelines>

    <Format>
        - Explain how you decided on the rank.
        - Then, provide the score like this: <score></score>
    </Format>
"""
