from qutils.llm.asynchronous import invoke

executives = """{
    "C-suites": [
        "Chief Executive Officer",
        "CEO",
        "Chief Operating Officer",
        "COO",
        "Chief Financial Officer",
        "CFO",
        "Chief Information Officer",
        "CIO",
        "Chief Technology Officer",
        "CTO",
        "Chief Marketing Officer",
        "CMO",
        "Chief Human Resources Officer",
        "CHRO",
        "Chief Compliance Officer",
        "CCO",
        "Chief Risk Officer",
        "CRO",
        "Chief Strategy Officer",
        "CSO",
        "Chief Innovation Officer",
        "CINO",
        "Chief Data Officer",
        "CDO",
        "Chief Product Officer",
        "CPO",
        "Chief Revenue Officer",
        "CRO",
        "Chief Customer Officer",
        "CCO",
        "Chief Legal Officer",
        "CLO",
        "Chief Administrative Officer",
        "CAO",
        "Chief Communications Officer",
        "CCO",
        "Chief Diversity Officer",
        "CDO",
        "Chief Investment Officer",
        "CIO",
        "Chief Development Officer",
        "CDO",
        "Chief Privacy Officer",
        "CPO",
        "Chief Ethics Officer",
        "CEO",
        "Chief Digital Officer",
        "CDO",
        "Chief Sustainability Officer",
        "CSO"
    ],
    "Presidents": [
        "President"
    ],
    "Founders": [
        "Founder"
    ],
    "Executive Vice Presidents": [
        "Executive Vice President",
        "EVP",
        "Executive VP"
    ],
    "Senior Vice Presidents": [
        "Senior Vice President",
        "SVP",
        "Senior VP",
        "Sr. VP"
    ],
    "Vice Presidents": [
        "Vice President",
        "VP"
    ],
    "Corporate Vice Presidents": [
        "Corporate Vice President",
        "CVP",
        "Corporate VP"
    ],
    "Associate Vice Presidents": [
        "Associate Vice President",
        "AVP",
        "Associate VP"
    ],
    "Regional Vice Presidents": [
        "Regional Vice President",
        "RVP",
        "Regional VP"
    ],
    "Group Vice Presidents": [
        "Group Vice President",
        "GVP",
        "Group VP"
    ],
    "Senior Directors": [
        "Senior Director",
        "Sr. Director"
    ],
    "Executive Directors": [
        "Executive Director",
        "Exec Director"
    ],
    "Corporate Directors": [
        "Corporate Director"
    ],
    "Managing Directors": [
        "Managing Director",
        "MD"
    ],
    "Regional Directors": [
        "Regional Director",
        "Area Director"
    ],
    "Directors": [
        "Director"
    ],
    "Associate Directors": [
        "Associate Director"
    ],
    "Non Executive Directors": [
        "Non Executive Director"
    ],
    "General Managers": [
        "General Manager",
        "GM"
    ],
    "Heads": [
        "Head"
    ],
    "Board Members": [
        "Board Member"
    ],
    "Chairmen": [
        "Chairman",
        "Chairman of the Board",
        "Chair"
    ],
    "Vice Chairmen": [
        "Vice Chairman",
        "Vice Chair"
    ],
    "Non Executive Chairmen": [
        "Non-Executive Chairman",
        "Non-Exec Chairman"
    ],
    "Executive Chairmen": [
        "Executive Chairman",
        "Exec Chairman"
    ],
    "Partners": [
        "Partner"
    ]
}"""


async def executive_or_not(title):
    if not title:
        return None

    messages = [
        {
            "role": "system",
            "content": f"""You are an intelligent assistant who will decide whether the title given to you is of an executive or not based on the information about executives provided to you.
            """,
        }
    ]

    user_query = f"""The following are json objects of executive titles to be used for this task. Consider all of these to be executives
            {executives}

            CONSIDER THE COMPLETE JSON OBJECT PROVIDED TO YOU! CONSIDER ALL THESE AS EXECUTIVES.
            Important: Titles quite similar to the ones above WILL ALSO BE EXECUTIVES. For example, the "Director of creative arts" will also be an executive as Director is listed in the json object.

            These titles or similar ones would be executives ALWAYS. 

            Instructions: Return only a 'Yes' or 'No'. A 'Yes' will mean the title is of an executive. A 'No' will mean the title isn't of an executives. 

            Example Input: Senior Vice preisident and founder
            Output : Yes

            Example Input: Project Manager
            Output: No

            Only return a Yes or a No in your output. Do not add any other text.
            
            """

    messages.append({"role": "user", "content": user_query + str(title)})

    completion = await invoke(
        messages=messages,
        temperature=0,
        model="openai/gpt-4o-mini",
        fallbacks=["anthropic/claude-3-5-haiku-latest"],
    )
    return completion
