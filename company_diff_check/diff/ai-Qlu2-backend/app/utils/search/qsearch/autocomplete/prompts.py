DATA_DICT = {
    "job titles": [
        {
            "input": "chi",
            "output": [
                "Chief Executive Officer",
                "Chief Operating Officer",
                "Chief Financial Officer",
                "Chief Technology Officer",
                "Chief Information Officer",
                "Chief Marketing Officer",
                "Chief Human Resources Officer",
                "Chief Communications Officer",
                "Chief Legal Officer",
                "Chief Security Officer",
                "Chief Diversity Officer",
                "Chief Revenue Officer",
                "Chief Customer Officer",
                "Chief Quality Officer",
                "Chief Visionary Officer",
            ],
        }
    ],
    "industries": [
        {
            "input": "mach",
            "output": [
                "Machinery",
                "Machine Tools",
                "Machining and Fabrication",
                "Machined Parts",
                "Machinery and Equipment",
                "Machining Services",
                "Machining and Precision",
                "Machine Vision",
                "Machine Automation",
                "Machine Learning",
                "Machine Intelligence",
                "Machine Vision",
                "Machine Tool Builders",
                "Machine Component",
                "Machine Shop",
            ],
        }
    ],
    "skills": [
        {
            "input": "no",
            "output": [
                "Node.js",
                "Nonverbal Communication",
                "Numerical Analysis",
                "Network Security",
                "Negotiation",
                "Nursing",
                "Natural Language Processing",
                "Nutrition",
                "Network Administration",
                "Neural Networks",
                "Nonprofit Management",
                "News Writing",
                "Noise Control",
                "New Product Development",
                "Nuclear Physics",
            ],
        }
    ],
    "majors": [
        {
            "input": "com",
            "output": [
                "Computer Science",
                "Computer Engineering",
                "Communication Studies",
                "Computational Biology",
                "Comparative Literature",
            ],
        }
    ],
    "degrees": [
        {
            "input": "doctor",
            "output": [
                "Doctor's Degree",
                "Doctor of Arts",
                "Doctor of Education - EdD",
                "Doctor of Law",
                "Doctor of Law - JD",
                "Doctor of Medicine - MD",
                "Doctor of Pharmacy - PharmD",
                "Doctor of Philosophy - PhD",
                "Doctor of Business Administration - DBA",
                "Doctor of Dental Surgery - DDS",
                "Doctor of Veterinary Medicine - DVM",
                "Doctor of Psychology - PsyD",
                "Doctor of Nursing Practice - DNP",
                "Doctor of Physical Therapy - DPT",
                "Doctor of Science - ScD",
            ],
        },
        {
            "input": "bach",
            "output": [
                "Bachelor's Degree",
                "Bachelor of Arts - BA",
                "Bachelor of Science - BS",
                "Bachelor of Business Administration - BBA",
                "Bachelor of Engineering - BE",
                "Bachelor of Technology - BTech",
                "Bachelor of Fine Arts - BFA",
                "Bachelor of Architecture - BArch",
                "Bachelor of Medicine - MBBS",
                "Bachelor of Laws - LLB",
                "Bachelor of Education - BEd",
                "Bachelor of Commerce - BCom",
                "Bachelor of Computer Science - BCS",
                "Bachelor of Social Work - BSW",
                "Bachelor of Music - BM",
            ],
        },
        {
            "input": "mas",
            "output": [
                "Master's Degree",
                "Master of Arts - MA",
                "Master of Science - MS",
                "Master of Business Administration - MBA",
                "Master of Engineering - MEng",
                "Master of Education - MEd",
                "Master of Fine Arts - MFA",
                "Master of Public Health - MPH",
                "Master of Social Work - MSW",
                "Master of Laws - LLM",
                "Master of Public Administration - MPA",
                "Master of Architecture - MArch",
                "Master of Computer Applications - MCA",
                "Master of Library Science - MLS",
                "Master of Divinity - MDiv",
            ],
        },
        {
            "input": "ass",
            "output": [
                "Associate's Degree",
                "Associate of Arts - AA",
                "Associate of Science - AS",
                "Associate of Applied Science - AAS",
                "Associate of Business Administration - ABA",
                "Associate of Engineering - AE",
                "Associate of Nursing - AN",
                "Associate of General Studies - AGS",
                "Associate of Occupational Studies - AOS",
                "Associate of Technology - AT",
            ],
        },
    ],
}


DEGREE_SYSTEM_PROMPT = """
You are an AI assistant designed to function as a highly accurate and efficient autocomplete system for academic degrees.

Your primary purpose is to predict and suggest the full, correct names of academic degrees based on partial user input.

**Instructions:**

1.  **Analyze Input:** Carefully examine the user's partial input string.
2.  **Predict and Suggest:** Based on the input, generate a list of the most relevant and common academic degree titles that match.
3.  **Prioritize Common Degrees:** Give priority to more common and widely recognized degrees that people use on LinkedIn (e.g., "Doctor of Philosophy - PhD", "Master of Business Administration - MBA", "Bachelor of Science - BS").
4.  **Include Variations:** Provide common variations and abbreviations where applicable (e.g., for "Doctor", suggest "Doctor of Medicine - MD", "Doctor of Law - JD", "Doctor of Education - EdD").
5.  **Format Output:** Return the suggestions as a JSON object with a single key, "keywords", which contains a list of the suggested degree strings. Do not add any extra text or explanations outside of the JSON object.
6.  **Be Fast and Concise:** Your response should be immediate and contain only the JSON output.

**Example Interaction:**

* **User Input:** `bach`
* **Your Expected Output:**
    ```json
    {
        "keywords": [
            "Bachelor's Degree",
            "Bachelor of Arts",
            "Bachelor of Arts - BA",
            "Bachelor of Business Administration",
            "Bachelor of Business Administration - BBA",
            "Bachelor of Applied Science",
            "Bachelor of Applied Science - BAS",
            "Bachelor of Commerce",
            "Bachelor of Commerce - BCom",
            "Bachelor of Engineering",
            "Bachelor of Engineering - BE",
            "Bachelor of Fine Arts",
            "Bachelor of Fine Arts - BFA",
            "Bachelor of Architecture",
            "Bachelor of Architecture - BArch",
            "Bachelor of Computer Science",
            "Bachelor of Computer Science - BCS"
        ]
    }
    ```

* **User Input:** `doctor`
* **Your Expected Output:**
    ```json
    {
        "keywords": [
            "Doctor's Degree",
            "Doctor of Arts",
            "Doctor of Arts - DA",
            "Doctor of Education",
            "Doctor of Education - EdD",
            "Doctor of Law",
            "Doctor of Law - JD",
            "Doctor of Medicine",
            "Doctor of Medicine - MD",
            "Doctor of Philosophy",
            "Doctor of Philosophy - PhD",
            "Doctor of Science",
            "Doctor of Science - DSc"
        ]
    }
    ```

* **User Input:** `master of sc`
* **Your Expected Output:**
    ```json
    {
        "keywords": [
            "Master of Science",
            "Master of Science - MS",
        ]
    }
    ```

Maintain a professional and neutral tone. Your sole function is to provide accurate autocomplete suggestions for academic degrees.
"""


def prompt_template(entity_category, starting_letters):
    if entity_category == "degrees":
        user_content = f'"{starting_letters}"'
        chat_history = [
            {"role": "system", "content": DEGREE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
    else:
        introduction = "Assist executive recruiters by providing information."
        instruction = (
            f"Identify if any '{entity_category}' begin with the letters '{starting_letters}'.\n\n"
            "List up to 10 corresponding items, if available. Give the most common ones first\n\n"
            f"Present your answers as separate lines of {entity_category}."
        )
        if entity_category == "skills" or entity_category == "industries":
            instruction += (
                f"\nDon't generate any {entity_category} greater than 2 words."
            )

        chat_history = [
            {"role": "system", "content": introduction},
            {"role": "user", "content": instruction},
        ]

    return chat_history
