from app.utils.ai_search_context.context_prompts import *
import os, anthropic, re

# from qutils.llm.utilities import asynchronous_llm
from qutils.llm.asynchronous import invoke


client = anthropic.AsyncAnthropic(
    api_key=os.getenv("ANTHROPIC_KEY"),
)


async def claude(messages, retries=3):

    for i in range(retries):
        try:
            response = await invoke(
                messages=messages,
                temperature=0.1,
                model="anthropic/claude-sonnet-4-20250514",
                fallbacks=["openai/gpt-4.1"],
            )
            response = (
                response.replace("null", "None")
                .replace("Bachelor's", "Bachelors")
                .replace("Master's", "Masters")
                .replace("false", "False")
                .replace("true", "True")
            )
            # print("-"*50)
            # print(response)
            # print("-"*50, "\n\n")
            response = (
                response[response.rfind("<Output>") : response.rfind("</Output>")]
                .replace("<Output>", "")
                .replace("<", "")
            )
            response = response[response.find("{") : response.rfind("}") + 1]
            response = eval(response.strip())
            return response
        except Exception as e:
            raise e
            pass
    return {}


def transform_data(input_data, demoBlocked=False):
    def transform_context(context, flag, demoBlocked=False):
        if not isinstance(context, dict):
            return {}

        transformed = {}

        # Transform title
        title_data = context.get("title", {})
        if isinstance(title_data, dict):
            transformed["title"] = {
                "event": title_data.get("event", ""),
                "filter": list(title_data.get("filter", {}).keys()),
            }
        else:
            transformed["title"] = {"event": "", "filter": []}

        # Transform management_level
        mgmt_data = context.get("management_level", {})
        if isinstance(mgmt_data, dict) and mgmt_data.get("filter"):
            transformed["management_level"] = {
                "event": mgmt_data.get("event", ""),
                "filter": list(mgmt_data.get("filter", {}).keys()),
            }
        else:
            transformed["management_level"] = {}

        if flag:
            industry = context.get("industry", {})
            if isinstance(industry, dict) and industry.get("filter"):
                transformed["industry"] = {"event": industry.get("event", "")}
                transformed["industry"]["excluded"] = [
                    item
                    for item in industry.get("filter", {}).keys()
                    if industry.get("filter", {}).get(item, {}).get("exclusion")
                ]
                transformed["industry"]["included"] = [
                    item
                    for item in industry.get("filter", {}).keys()
                    if item not in transformed["industry"]["excluded"]
                ]
            else:
                transformed["industry"] = {}

        # Transform simple list fields
        simple_fields = ["name", "education", "school", "ownership"]
        for field in simple_fields:
            value = context.get(field, [])
            transformed[field] = value if isinstance(value, list) else []

        # Transform numeric range fields
        range_fields = ["experience", "role_tenure", "company_tenure"]
        for field in range_fields:
            field_data = context.get(field, {})
            if (
                isinstance(field_data, dict)
                and "min" in field_data
                and "max" in field_data
            ):
                try:
                    transformed[field] = f"{field_data['min']}-{field_data['max']}"
                except (TypeError, ValueError):
                    transformed[field] = {}
            else:
                transformed[field] = {}

        # Transform location
        location_data = context.get("location", {})
        transformed["location"] = (
            location_data if isinstance(location_data, dict) else {}
        )

        # Transform skills
        skill_data = context.get("skill", {})
        if isinstance(skill_data, dict) and isinstance(skill_data.get("filter"), dict):
            transformed["skill"] = {}
            transformed["skill"]["Good to have skills"] = list(
                key
                for key, value in skill_data.get("filter", {}).items()
                if value.get("state", "") == "include"
            )
            transformed["skill"]["Must have skills"] = list(
                key
                for key, value in skill_data.get("filter", {}).items()
                if value.get("state", "") == "must-include"
            )
            transformed["skill"]["Excluded skills"] = list(
                key
                for key, value in skill_data.get("filter", {}).items()
                if value.get("state", "") == "exclude"
            )
        else:
            transformed["skill"] = []

        # Add gender if present ,
        # Transform simple list fields
        if not demoBlocked:
            simple_fields_demo = ["age", "ethnicity"]
            for field in simple_fields_demo:
                value = context.get(field, [])
                transformed[field] = value if isinstance(value, list) else []

            gender = context.get("gender")
            if gender:
                transformed["gender"] = gender

        companies = context.get("companies")
        transformed["companies"] = {"current": [], "past": [], "event": ""}
        if companies:
            transformed["companies"]["current"] = ""
            transformed["companies"]["past"] = ""

            for item in companies["current"]:
                transformed["companies"]["current"] += item["prompt"]
            for item in companies["past"]:
                transformed["companies"]["past"] += item["prompt"]
            transformed["companies"]["event"] = companies["event"]

        products = context.get("products")
        transformed["products"] = {"current": [], "past": [], "event": ""}
        if products:
            transformed["products"]["current"] = ""
            transformed["products"]["past"] = ""

            for item in products["current"]:
                transformed["companies"]["current"] += item["prompt"]
            for item in products["past"]:
                transformed["products"]["past"] += item["prompt"]
            transformed["products"]["event"] = products["event"]

        return transformed

    transformed_queries = []

    industry_flag = (
        True
        if input_data[len(input_data) - 1].get("context", {}).get("industry", None)
        else False
    )

    for index in range(len(input_data) - 1, -1, -1):
        item = input_data[index]
        if not isinstance(item, dict):
            continue

        transformed_query = {
            "query": item.get("query", ""),
            "context": transform_context(
                item.get("context", {}), industry_flag, demoBlocked
            ),
        }
        transformed_queries = [transformed_query] + transformed_queries

    output = transformed_queries
    return output, industry_flag


async def Evaluate_Extract_Modify(prompt, queries, demoBlocked=False):
    key_mapping = {
        "job_role": "jobRole",
        "company_industry_product": "companyProduct",
        "company_product": "companyProduct",
        "total_working_years": "totalYears",
        "name": "educName",
        "education": "educName",
        "skills": "skill",
    }

    queries, industry_flag = transform_data(queries, demoBlocked)
    older_queries = {}
    for index, element in enumerate(queries):
        older_queries[index] = element

    if not industry_flag:
        selected_prompt = EVALUATE_FILTERS_USER_PROMPT
    else:
        selected_prompt = EVALUATE_FILTERS_USER_INDUSTRY_BACKUP_PROMPT

    demographics = "• demographics: Gender, age, ethnicity." if not demoBlocked else ""
    selected_prompt = re.sub(r"{demographics}", demographics, selected_prompt)

    demo_in_list = ", demographics" if not demoBlocked else ""
    selected_prompt = re.sub(r"{Add_Demo_Option}", demo_in_list, selected_prompt)

    reminder = ""
    if len(queries) > 5:
        if not industry_flag:
            reminder = "Remember that your output can only contain the following filters if required: [job_role, company_industry_product, skill, location, total_working_years, education, name, ownership, demographics]"
        else:
            reminder = "Remember that your output can only contain the following filters if required: [job_role, company_product, skill, location, total_working_years, education, name, ownership, demographics]"

    user_prompt = f"""
<Older_queries>
    {older_queries}
</Older_queries>
{reminder}
<New_Query>
    {prompt}
</New_Query>

Understand the prompt step by step and read all the examples.
"""
    messages = [
        {"role": "system", "content": selected_prompt},
        {"role": "user", "content": user_prompt},
    ]
    response = await claude(messages)

    response["action"] = (
        response["action"].lower() if "action" in response else "modify"
    )
    allowed_filters = [
        "jobRole",
        "companyProduct",
        "totalYears",
        "educName",
        "skill",
        "industry",
        "location",
        "name",
        "ownership",
    ]
    if not demoBlocked:
        allowed_filters.append("demographics")

    if "filters" in response:
        filters = [
            key_mapping[key] if key in key_mapping else key
            for key in response["filters"]
        ]

        response["filters"] = [item for item in filters if item in allowed_filters]

        response["filters"] = list(set(response["filters"]))

        if (
            "companyIndustry" not in response["filters"]
            and "rephrased_query" in response
        ):
            del response["rephrased_query"]
        elif (
            "companyIndustry" in response["filters"]
            and "rephrased_query" not in response
        ):
            response["filters"].remove("companyIndustry")
        elif "rephrased_query" in response:
            response["rephrasedQuery"] = response["rephrased_query"]
            del response["rephrased_query"]

    if not response.get("indexes", []):
        if "jobRole" in response.get("filters", []) and "skill" not in response.get(
            "filters", []
        ):
            response.get("filters", []).append("skill")

    if "indexes" not in response:
        response["indexes"] = []
    response["indexes"] = [item for item in response["indexes"] if item < len(queries)]
    if "filters" not in response or response["action"] == "extract":
        response["filters"] = []

    if "reasoning" in response:
        del response["reasoning"]
    return response


def reverse_output_to_input(output_data):
    input_data = {}
    levels_mapping = {
        "C-Suite/Chiefs": "C Suite",
        "President": "President",
        "Executive VP or Sr. VP": "Executive and Sr. VP",
        "Founder or Co-founder": "Founder/Co-Founder",
        "Senior (All Senior-Level Individual Contributors)": "Senior (Individual Contributor)",
        "Mid (All Mid-Level Individual Contributors)": "Mid (Individual Contributor)",
        "Junior (All Junior-Level Individual Contributors)": "Junior",
    }

    if "school" in output_data:
        input_data["school"] = output_data.get("school", [])

    # Reverse education
    if "education" in output_data:
        input_data["education"] = output_data.get("education", [])

    # Reverse experience
    if "experience" in output_data:
        input_data["experience"] = (
            {
                "min": output_data["experience"].get("min"),
                "max": output_data["experience"].get("max"),
            }
            if output_data["experience"]
            and (
                output_data["experience"].get("max", 1)
                - output_data["experience"].get("min", 1)
                <= 59
                or output_data["experience"].get("min", 1) >= 2
            )
            else None
        )
        if input_data["experience"].get("max", 60) < input_data["experience"].get(
            "min", 0
        ):
            input_data["experience"]["max"] = (
                input_data["experience"].get("min", 0) + 2
                if input_data["experience"].get("min", 0) < 99
                else input_data["experience"].get("min", 0)
            )

    if "company_tenure" in output_data:
        input_data["company_tenure"] = (
            {
                "min": output_data["company_tenure"].get("min"),
                "max": output_data["company_tenure"].get("max"),
            }
            if output_data["company_tenure"]
            and (
                output_data["company_tenure"].get("max", 1)
                - output_data["company_tenure"].get("min", 1)
                <= 59
            )
            else None
        )
        if input_data["company_tenure"].get("max", 60) < input_data[
            "company_tenure"
        ].get("min", 0):
            input_data["company_tenure"]["max"] = (
                input_data["company_tenure"].get("min", 0) + 2
                if input_data["company_tenure"].get("min", 0) < 99
                else input_data["company_tenure"].get("min", 0)
            )

    if "role_tenure" in output_data:
        input_data["role_tenure"] = (
            {
                "min": output_data["role_tenure"].get("min"),
                "max": output_data["role_tenure"].get("max"),
            }
            if output_data["role_tenure"]
            and (
                output_data["role_tenure"].get("max", 1)
                - output_data["role_tenure"].get("min", 1)
                <= 59
            )
            else None
        )

        if input_data["role_tenure"].get("max", 60) < input_data["role_tenure"].get(
            "min", 0
        ):
            input_data["role_tenure"]["max"] = (
                input_data["role_tenure"].get("min", 0) + 2
                if input_data["role_tenure"].get("min", 0) < 99
                else input_data["role_tenure"].get("min", 0)
            )

    if "job_title" in output_data:  # Note: changed from "title" to "job_title"

        common_elements = {}
        current_titles = output_data["job_title"].get("Current", [])
        past_titles = output_data["job_title"].get("Past", [])
        both_titles = output_data["job_title"].get("Both", [])

        # Find common elements based on the "title_name" field
        for current in current_titles:
            current_name = current.get("title_name")
            if current_name:
                for past in past_titles:
                    if current_name == past.get("title_name"):
                        # Combine min and max values from Current and Past
                        common_elements[current_name] = {
                            "title_name": current_name,
                            "min_staff": min(
                                current.get(
                                    "min_staff", float("inf")
                                ),  # Updated field name
                                past.get(
                                    "min_staff", float("inf")
                                ),  # Updated field name
                            ),
                            "max_staff": max(
                                current.get(
                                    "max_staff", float("-inf")
                                ),  # Updated field name
                                past.get(
                                    "max_staff", float("-inf")
                                ),  # Updated field name
                            ),
                            "exclusion": current.get("exclusion", False)
                            and past.get(
                                "exclusion", False
                            ),  # New field: True if both are True
                        }

        # Update "Both" with common elements
        both_names = {item.get("title_name") for item in both_titles}
        for common in common_elements.values():
            if common["title_name"] not in both_names:
                both_titles.append(common)

        # Update "Current" to remove common elements
        output_data["job_title"]["Current"] = [
            item
            for item in current_titles
            if item.get("title_name") not in common_elements
        ]

        # Update "Past" to remove common elements
        output_data["job_title"]["Past"] = [
            item
            for item in past_titles
            if item.get("title_name") not in common_elements
        ]

        # Update "Both" in the output
        output_data["job_title"]["Both"] = both_titles

        current = output_data["job_title"].get("Current", [])
        past = output_data["job_title"].get("Past", [])
        both = both_titles

        input_data["title"] = {"event": None, "filter": {}}
        if current and not past and not both:
            input_data["title"]["event"] = "CURRENT"
        elif past and not current and not both:
            input_data["title"]["event"] = "PAST"
        else:
            input_data["title"]["event"] = (
                "AND"
                if "AND" in output_data["job_title"].get("Event", "").upper()
                else "OR"
            )

        input_data["title"]["filter"].update(
            {
                title["title_name"]: {
                    "min": title["min_staff"],
                    "max": title["max_staff"],
                    "exclusion": title.get("exclusion", False),  # New field
                    "type": "CURRENT",
                }
                for title in output_data["job_title"].get("Current", [])
            }
        )
        input_data["title"]["filter"].update(
            {
                title["title_name"]: {
                    "min": title["min_staff"],
                    "max": title["max_staff"],
                    "exclusion": title.get("exclusion", False),  # New field
                    "type": "PAST",
                }
                for title in output_data["job_title"].get("Past", [])
            }
        )
        input_data["title"]["filter"].update(
            {
                title["title_name"]: {
                    "min": title["min_staff"],
                    "max": title["max_staff"],
                    "exclusion": title.get("exclusion", False),  # New field
                    "type": "BOTH",
                }
                for title in output_data["job_title"].get("Both", [])
            }
        )

        if not input_data["title"]["filter"]:
            input_data["title"] = {}

    # Reverse management_levels
    if "management_level" in output_data:

        possible_levels = [
            "Partners",
            "Founder/Co-Founder",
            "Board of Directors",
            "C Suite",
            "Head",
            "President",
            "Executive and Sr. VP",
            "General Manager",
            "VP",
            "Director",
            "Manager",
            "Senior (Individual Contributor)",
            "Mid (Individual Contributor)",
            "Junior",
        ]

        common_elements = set(output_data["management_level"].get("Current", [])) & set(
            output_data["management_level"].get("Past", [])
        )
        both = output_data["management_level"].get("Both", [])
        both.extend(
            item
            for item in common_elements
            if item not in output_data["management_level"].get("Both", [])
        )
        output_data["management_level"]["Both"] = both

        output_data["management_level"]["Current"] = [
            item
            for item in output_data["management_level"].get("Current", [])
            if item not in common_elements
        ]
        output_data["management_level"]["Past"] = [
            item
            for item in output_data["management_level"].get("Past", [])
            if item not in common_elements
        ]

        current = [
            item
            for item in output_data["management_level"].get("Current", [])
            if item in possible_levels
        ]
        past = [
            item
            for item in output_data["management_level"].get("Past", [])
            if item in possible_levels
        ]
        both = [
            item
            for item in output_data["management_level"].get("Both", [])
            if item in possible_levels
        ]

        input_data["management_level"] = {"event": None}

        if current and not past and not both:
            input_data["management_level"]["event"] = "CURRENT"
        elif past and not current and not both:
            input_data["management_level"]["event"] = "PAST"
        else:
            # input_data["management_level"]["event"] = (
            #     output_data["management_level"].get("Event").upper()
            #     if output_data["management_level"].get("Event").upper() in ["AND", "OR"]
            #     else "OR"
            # )
            input_data["management_level"]["event"] = (
                "AND"
                if "AND" in output_data["management_level"].get("Event").upper()
                else "OR"
            )
        input_data["management_level"]["filter"] = {
            levels_mapping.get(level, level): {"type": "CURRENT"}
            for level in output_data["management_level"].get("Current", [])
            if levels_mapping.get(level, level) in possible_levels
        }

        input_data["management_level"]["filter"].update(
            {
                levels_mapping.get(level, level): {"type": "PAST"}
                for level in output_data["management_level"].get("Past", [])
                if levels_mapping.get(level, level) in possible_levels
            }
        )
        input_data["management_level"]["filter"].update(
            {
                levels_mapping.get(level, level): {"type": "BOTH"}
                for level in output_data["management_level"].get("Both", [])
                if levels_mapping.get(level, level) in possible_levels
            }
        )

    # Reverse skills
    if "skill" in output_data:
        input_data["skill"] = (
            {
                "event": "OR",
                "filter": {
                    # **{
                    #     skill: {"state": "must-include", "type": "CURRENT"}
                    #     for skill in output_data["skill"].get("must_have", [])
                    # },
                    **{
                        skill: {"state": "include", "type": "CURRENT"}
                        for skill in output_data["skill"].get("included", [])
                    },
                    **{
                        skill: {"state": "exclude", "type": "CURRENT"}
                        for skill in output_data["skill"].get("excluded", [])
                    },
                },
            }
            if output_data.get("skill")  # Ensures `output_data["skill"]` exists
            else {}
        )

    if "industry" in output_data:
        temp_data = {"industry": {"event": "OR", "relation": "OR", "filter": {}}}

        # Mapping the type based on keys in output_data
        output_to_type = {"current": "CURRENT", "past": "PAST", "both": "BOTH"}

        # Populate the filter in input_data
        for key in output_to_type.keys():
            type_value = output_to_type[key]
            included = output_data["industry"].get(key, {}).get("included", [])
            excluded = output_data["industry"].get(key, {}).get("excluded", [])

            # Add included industries
            for industry in included:
                temp_data["industry"]["filter"].setdefault(
                    industry, {"type": type_value, "exclusion": False}
                )

            # Add excluded industries
            for industry in excluded:
                temp_data["industry"]["filter"].setdefault(
                    industry, {"type": type_value, "exclusion": True}
                )

        # Set the event field based on 'event' in output_data

        industry_events = ["AND"]

        if (
            output_data["industry"].get("current", {}).get("included", [])
            or output_data["industry"].get("current", {}).get("excluded", [])
        ) and not (
            output_data["industry"].get("past", {}).get("included", [])
            or output_data["industry"].get("past", {}).get("excluded", [])
        ):
            temp_data["industry"]["event"] = "CURRENT"
        elif not (
            output_data["industry"].get("current", {}).get("included", [])
            or output_data["industry"].get("current", {}).get("excluded", [])
        ) and (
            output_data["industry"].get("past", {}).get("included", [])
            or output_data["industry"].get("past", {}).get("excluded", [])
        ):
            temp_data["industry"]["event"] = "PAST"
        else:
            temp_data["industry"]["event"] = (
                "AND"
                if "and" in output_data["industry"].get("event", "OR").lower()
                else "OR"
            )

        if temp_data["industry"]["filter"]:
            input_data["industry"] = temp_data["industry"]

    if "location" in output_data:
        # Handle common elements between Current and Past (move to Both)
        current_include = set(
            output_data["location"].get("Current", {}).get("include", [])
        )
        past_include = set(output_data["location"].get("Past", {}).get("include", []))
        current_exclude = set(
            output_data["location"].get("Current", {}).get("exclude", [])
        )
        past_exclude = set(output_data["location"].get("Past", {}).get("exclude", []))

        # Find common elements in include lists
        common_include_elements = current_include & past_include
        both_include = output_data["location"].get("Both", {}).get("include", [])
        both_include.extend(
            item
            for item in common_include_elements
            if item not in output_data["location"].get("Both", {}).get("include", [])
        )

        # Find common elements in exclude lists
        common_exclude_elements = current_exclude & past_exclude
        both_exclude = output_data["location"].get("Both", {}).get("exclude", [])
        both_exclude.extend(
            item
            for item in common_exclude_elements
            if item not in output_data["location"].get("Both", {}).get("exclude", [])
        )

        # Update the Both include and exclude lists
        if "Both" not in output_data["location"]:
            output_data["location"]["Both"] = {"include": [], "exclude": []}
        output_data["location"]["Both"]["include"] = both_include
        output_data["location"]["Both"]["exclude"] = both_exclude

        # Remove common elements from Current and Past include lists
        output_data["location"]["Current"]["include"] = [
            item
            for item in output_data["location"].get("Current", {}).get("include", [])
            if item not in common_include_elements
        ]
        output_data["location"]["Past"]["include"] = [
            item
            for item in output_data["location"].get("Past", {}).get("include", [])
            if item not in common_include_elements
        ]

        # Remove common elements from Current and Past exclude lists
        output_data["location"]["Current"]["exclude"] = [
            item
            for item in output_data["location"].get("Current", {}).get("exclude", [])
            if item not in common_exclude_elements
        ]
        output_data["location"]["Past"]["exclude"] = [
            item
            for item in output_data["location"].get("Past", {}).get("exclude", [])
            if item not in common_exclude_elements
        ]

        # Expand continental locations for each timeline
        continental_expansions = {
            "South America": [
                "Argentina",
                "Bolivia",
                "Brazil",
                "Chile",
                "Colombia",
                "Ecuador",
                "Guyana",
                "Paraguay",
                "Peru",
                "Suriname",
                "Uruguay",
                "Venezuela",
            ],
            "North America": [
                "Antigua and Barbuda",
                "Bahamas",
                "Barbados",
                "Belize",
                "Canada",
                "Costa Rica",
                "Cuba",
                "Dominica",
                "Dominican Republic",
                "El Salvador",
                "Grenada",
                "Guatemala",
                "Haiti",
                "Honduras",
                "Jamaica",
                "Mexico",
                "Nicaragua",
                "Panama",
                "Saint Kitts and Nevis",
                "Saint Lucia",
                "Saint Vincent and the Grenadines",
                "Trinidad and Tobago",
                "United States",
            ],
            "Oceania": [
                "Australia",
                "Fiji",
                "Kiribati",
                "Marshall Islands",
                "Micronesia",
                "Nauru",
                "New Zealand",
                "Palau",
                "Papua New Guinea",
                "Samoa",
                "Solomon Islands",
                "Tonga",
                "Tuvalu",
                "Vanuatu",
            ],
        }

        for timeline in ["Current", "Both", "Past"]:
            if timeline in output_data["location"]:
                # Handle include list expansions
                include_list = output_data["location"][timeline].get("include", [])
                exclude_list = output_data["location"][timeline].get("exclude", [])

                # Expand continents in include list
                for continent, countries in continental_expansions.items():
                    if continent in include_list:
                        # Add countries that aren't already in the list
                        for country in countries:
                            if country not in include_list:
                                include_list.append(country)

                # Expand continents in exclude list
                for continent, countries in continental_expansions.items():
                    if continent in exclude_list:
                        # Add countries that aren't already in the list
                        for country in countries:
                            if country not in exclude_list:
                                exclude_list.append(country)

        # Initialize input_data structure
        input_data["location"] = {"event": None, "filter": {}}

        # Get all location lists
        current_include = output_data["location"].get("Current", {}).get("include", [])
        current_exclude = output_data["location"].get("Current", {}).get("exclude", [])
        past_include = output_data["location"].get("Past", {}).get("include", [])
        past_exclude = output_data["location"].get("Past", {}).get("exclude", [])
        both_include = output_data["location"].get("Both", {}).get("include", [])
        both_exclude = output_data["location"].get("Both", {}).get("exclude", [])

        # Determine event type - all locations (included and excluded) must be in same timeline for CURRENT/PAST
        has_current = bool(current_include or current_exclude)
        has_past = bool(past_include or past_exclude)
        has_both = bool(both_include or both_exclude)

        if has_current and not has_past and not has_both:
            input_data["location"]["event"] = "CURRENT"
        elif has_past and not has_current and not has_both:
            input_data["location"]["event"] = "PAST"
        else:
            input_data["location"]["event"] = next(
                (
                    item
                    for item in ["OR", "AND"]
                    if item in output_data["location"].get("Event", "").upper()
                ),
                "OR",
            )

        # Build filter with include locations
        for timeline, type_val in [
            ("Current", "CURRENT"),
            ("Past", "PAST"),
            ("Both", "BOTH"),
        ]:
            if timeline in output_data["location"]:
                # Handle include locations
                for location in output_data["location"][timeline].get("include", []):
                    input_data["location"]["filter"][location] = {
                        "type": type_val,
                        "exclusion": False,
                    }

                # Handle exclude locations
                for location in output_data["location"][timeline].get("exclude", []):
                    input_data["location"]["filter"][location] = {
                        "type": type_val,
                        "exclusion": True,
                    }

        if not input_data.get("location", {}).get("filter"):
            input_data["location"] = {}

    # Reverse names
    if "name" in output_data:
        input_data["name"] = output_data.get("name", [])

    if "age" in output_data:
        input_data["age"] = [
            item
            for item in output_data.get("age", [])
            if item in ["Under 25", "Over 50", "Over 65"]
        ]

    if "gender" in output_data:
        if isinstance(output_data["gender"], list):
            if (
                "female" in output_data.get("gender", [])
                or "Female" in output_data.get("gender", [])
            ) and len(output_data.get("gender", [])) == 1:
                input_data["gender"] = "Female"
        elif isinstance(output_data["gender"], str):
            if "female" in output_data["gender"].lower():
                input_data["gender"] = "Female"

    if "ethnicity" in output_data:
        input_data["ethnicity"] = [
            item
            for item in output_data.get("ethnicity", [])
            if item in ["Asian", "African", "Hispanic", "Middle Eastern", "South Asian"]
        ]
        if "Black" in input_data["ethnicity"]:
            input_data["ethnicity"].remove("Black")
            if "African" not in input_data["ethnicity"]:
                input_data["ethnicity"].append("African")
        if "South East Asian" in input_data["ethnicity"]:
            input_data["ethnicity"].remove("South East Asian")
            if "South Asian" not in input_data["ethnicity"]:
                input_data["ethnicity"].append("South Asian")

        if "South East Asian" in input_data["ethnicity"]:
            input_data["ethnicity"].remove("South East Asian")
            if "South Asian" not in input_data["ethnicity"]:
                input_data["ethnicity"].append("South Asian")

    input_data["ownership"] = [
        item
        for item in output_data.get("ownership", [])
        if item in ["Public", "Private", "VC Funded", "Private Equity Backed"]
    ]

    input_data = {key: value for key, value in input_data.items() if value}
    return input_data


def clean_results(data):

    key_mapping = {
        "schools/universities": "school",
        "education": "education",
        "total_working_years": "experience",
        "job_titles": "job_title",
        "job_title": "job_title",
        "management_levels": "management_level",
        "skills": "skill",
        "locations": "location",
        "names": "name",
        "isExperienceSelected": "isExperienceSelected",  # Key added as requested
    }

    for key in [
        "job_titles",
        "management_levels",
        "locations",
        "job_title",
        "management_level",
        "location",
    ]:
        if key in data and all(
            not data[key][k] for k in ["Current", "Past", "Both"] if k in data[key]
        ):
            del data[key]

    if "industry" in data:
        key = "industry"
        del_flag = True
        for indus in ["current", "past", "both"]:
            if data[key].get(indus, {}).get("included", None) or not data[key].get(
                indus, {}
            ).get("excluded", None):
                del_flag = False

        if del_flag:
            del data[key]

    # if "management_levels" in data:
    #     possible_levels = [
    #         "Partners",
    #         "Founder/Co-Founder",
    #         "Board of Directors",
    #         "CSuite and President",
    #         "Executive and Sr. VP",
    #         "General Manager",
    #         "VP",
    #         "Director",
    #         "Manager",
    #         "Senior (Individual Contributor)",
    #         "Mid (Individual Contributor)",
    #         "Junior",
    #     ]
    #     for timeline in ["Current", "Past", "Both"]:
    #         if timeline in data["management_levels"] and data["management_levels"].get(
    #             timeline, []
    #         ):
    #             for level in list(data["management_levels"][timeline]):
    #                 if level not in possible_levels:
    #                     if "job_titles" not in data:
    #                         data["job_titles"] = {"Current": [], "Past": [], "Both": []}

    #                     if timeline not in data["job_titles"] or data["job_titles"].get(
    #                         timeline, []
    #                     ):
    #                         data["job_titles"][timeline] = []

    #                     data["job_titles"][timeline].append({"name" : level, "min" :300})

    #                     data["management_levels"][timeline].remove(level)

    if (
        "skill" in data
        and not data["skill"].get("included", [])
        and not data["skill"].get("excluded", [])
    ):
        del data["skill"]

    for key in ["schools/universities", "education", "names"]:
        if key in data and not data[key]:
            del data[key]
        elif key in data and key == "education":
            ind = []
            for index in range(len(data[key]) - 1, -1, -1):
                if (
                    "degree" in data[key][index]
                    and data[key][index].get("degree")
                    and data[key][index].get("degree")
                    in [
                        "Associate",
                        "Bachelors",
                        "Masters",
                        "Doctorate",
                        "Diploma",
                        "Certificate",
                        "Any",
                    ]
                ):
                    data[key][index]["degree"] = (
                        data[key][index]["degree"]
                        .replace("Bachelors", "Bachelor’s")
                        .replace("Masters", "Master’s")
                        .capitalize()
                        .strip()
                    )
                elif "degree" in data[key][index]:
                    del data[key][index]["degree"]

                if "major" in data[key][index] and data[key][index].get("major"):
                    data[key][index]["major"] = (
                        data[key][index]["major"].replace("'", "’").title()
                    )
                elif "major" in data[key][index]:
                    del data[key][index]["major"]

                if not data[key][index]:
                    del data[key][index]

    if "total_working_years" in data and (
        data["total_working_years"] == {"min": None, "max": None}
        or data["total_working_years"] == {"min": -1, "max": 60}
    ):
        del data["total_working_years"]

    if "role_tenure" in data and (
        data["role_tenure"] == {"min": None, "max": None}
        or data["role_tenure"] == {"min": 0, "max": 60}
    ):
        del data["role_tenure"]
    elif (
        "role_tenure" in data
        and ("min" in data["role_tenure"] and "max" in data["role_tenure"])
        and (data["role_tenure"]["min"] == data["role_tenure"]["max"])
    ):
        data["role_tenure"]["min"] -= 1
        data["role_tenure"]["max"] += 1

    if "company_tenure" in data and (
        data["company_tenure"] == {"min": None, "max": None}
        or data["company_tenure"] == {"min": 0, "max": 60}
    ):
        del data["company_tenure"]
    elif (
        "company_tenure" in data
        and ("min" in data["company_tenure"] and "max" in data["company_tenure"])
        and (data["company_tenure"]["min"] == data["company_tenure"]["max"])
    ):
        data["company_tenure"]["min"] -= 1
        data["company_tenure"]["max"] += 1

    data = {
        key_mapping[key] if key in key_mapping else key: value
        for key, value in data.items()
    }
    return data


async def format_results(queries, results, entity):
    user_prompt_1 = """
    - The first prompt was: {}.
    Its results are as followed:
    <Output>
    {}
    </Output>

    New prompt: {}
    """

    if len(results) < 2:
        user_prompt = user_prompt_1.format(queries[0], results[0], queries[-1])
        user_prompt = user_prompt + "\n Also tell your reasoning this time"
    else:
        user_prompt = user_prompt_1.format(queries[0], results[0], queries[1])

    if entity == "jobRole":
        # system_prompt = TITLES_MANAGEMENT_MODIFICATION_SYSTEM_PROMPT
        user_prompt = TITLES_MANAGEMENT_MODIFICATION_USER_PROMPT + user_prompt
    elif entity == "location":
        # system_prompt = LOCATIONS_MODIFICATION_SYSTEM_PROMPT
        user_prompt = LOCATIONS_MODIFICATION_USER_PROMPT + user_prompt
    elif entity == "skill":
        # system_prompt = SKILLS_MODIFICATION_SYSTEM_PROMPT
        user_prompt = SKILLS_MODIFICATION_USER_PROMPT + user_prompt
    elif entity == "educName":
        # system_prompt = EDUC_NAME_MODIFICATION_SYSTEM_PROMPT
        user_prompt = EDUC_NAME_MODIFICATION_USER_PROMPT + user_prompt
    elif entity == "totalYears":
        # system_prompt = TOTAL_YEARS_MODIFICATION_SYSTEM_PROMPT
        user_prompt = TOTAL_YEARS_MODIFICATION_USER_PROMPT + user_prompt
    elif entity == "demographics":
        user_prompt = DEMOGRAPHICS_MODIFICATION_USER_PROMPT + user_prompt
    elif entity == "ownership":
        user_prompt = OWNERSHIP_MODIFICATION_USER_PROMPT + user_prompt
    elif entity == "industry":
        user_prompt = INDUSTRY_MODIFICATION_USER_PROMPT + user_prompt
    else:
        raise ValueError("Invalid entity")

    messages = [
        # {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    for old_index in range(1, len(results)):
        temp = f"""
        <Output>
            {results[old_index]}
        </Output>
        """
        messages.append({"role": "assistant", "content": temp})
        if old_index + 1 == len(results):
            messages.append(
                {
                    "role": "user",
                    "content": "New prompt: "
                    + queries[old_index + 1]
                    + "\n Also tell your reasoning this time",
                }
            )
        else:
            messages.append(
                {"role": "user", "content": "New prompt: " + queries[old_index + 1]}
            )

    response = await claude(messages)
    return response


async def context(new_prompt, major_data, entity=None, return_entity=False):
    all_results = []
    all_old_prompts = []

    if entity in [
        "educName",
        "totalYears",
        "location",
        "skill",
        "jobRole",
        "demographics",
        "ownership",
        "industry",
    ]:
        for i in range(len(major_data)):
            data = major_data[i]
            input_data = data["result"]
            old_prompt = data["prompt"]

            if entity == "jobRole":
                output_data = {
                    "job_titles": {
                        "Current": (
                            [
                                {
                                    "title_name": title,
                                    "min_staff": details["min"],
                                    "max_staff": details["max"],
                                    "exclusion": details.get("exclusion"),
                                }
                                for title, details in input_data["title"][
                                    "filter"
                                ].items()
                                if details["type"] == "CURRENT"
                            ]
                            if input_data["title"]
                            and input_data.get("title").get("event") != "OR"
                            else []
                        ),
                        "Past": (
                            [
                                {
                                    "title_name": title,
                                    "min_staff": details["min"],
                                    "max_staff": details["max"],
                                    "exclusion": details.get("exclusion"),
                                }
                                for title, details in input_data["title"][
                                    "filter"
                                ].items()
                                if details["type"] == "PAST"
                            ]
                            if input_data["title"]
                            and input_data.get("title").get("event") != "OR"
                            else []
                        ),
                        "Both": (
                            [
                                {
                                    "title_name": title,
                                    "min_staff": details["min"],
                                    "max_staff": details["max"],
                                    "exclusion": details.get("exclusion"),
                                }
                                for title, details in input_data["title"][
                                    "filter"
                                ].items()
                                if details["type"] == "BOTH"
                                or input_data.get("title").get("event") == "OR"
                            ]
                            if input_data["title"]
                            else []
                        ),
                        "Event": (
                            input_data["title"]["event"]
                            if input_data["title"]
                            else None
                        ),
                    },
                    "management_levels": {
                        "Current": (
                            [
                                level
                                for level, details in input_data["management_level"][
                                    "filter"
                                ].items()
                                if details["type"] == "CURRENT"
                            ]
                            if input_data["management_level"]
                            and input_data.get("management_level").get("event") != "OR"
                            else []
                        ),
                        "Past": (
                            [
                                level
                                for level, details in input_data["management_level"][
                                    "filter"
                                ].items()
                                if details["type"] == "PAST"
                            ]
                            if input_data["management_level"]
                            and input_data.get("management_level").get("event") != "OR"
                            else []
                        ),
                        "Both": (
                            [
                                level
                                for level, details in input_data["management_level"][
                                    "filter"
                                ].items()
                                if details["type"] == "BOTH"
                                or input_data.get("management_level").get("event")
                                == "OR"
                            ]
                            if input_data["management_level"]
                            else []
                        ),
                        "Event": (
                            input_data["management_level"]["event"]
                            if input_data["management_level"]
                            else None
                        ),
                    },
                }
            elif entity == "skill":
                output_data = {
                    "skill": {
                        "must_have": (
                            [
                                skill
                                for skill, details in input_data["skill"][
                                    "filter"
                                ].items()
                                if details["state"] == "must-include"
                            ]
                            if input_data["skill"]
                            else []
                        ),
                        "good_to_have": (
                            [
                                skill
                                for skill, details in input_data["skill"][
                                    "filter"
                                ].items()
                                if details["state"] == "include"
                            ]
                            if input_data["skill"]
                            else []
                        ),
                        "excluded": (
                            [
                                skill
                                for skill, details in input_data["skill"][
                                    "filter"
                                ].items()
                                if details["state"] == "exclude"
                            ]
                            if input_data["skill"]
                            else []
                        ),
                    }
                }
            elif entity == "industry":
                output_data = {
                    "industry": {
                        "current": {
                            "included": (
                                [
                                    skill
                                    for skill, details in input_data["industry"][
                                        "filter"
                                    ].items()
                                    if not details["exclusion"]
                                    and details.get("type", "").lower() == "current"
                                ]
                                if input_data["industry"]
                                and input_data.get("industry").get("event") != "OR"
                                else []
                            ),
                            "excluded": (
                                [
                                    skill
                                    for skill, details in input_data["industry"][
                                        "filter"
                                    ].items()
                                    if details["exclusion"]
                                    and details.get("type", "").lower() == "current"
                                ]
                                if input_data["industry"]
                                and input_data.get("industry").get("event") != "OR"
                                else []
                            ),
                        },
                        "past": {
                            "included": (
                                [
                                    skill
                                    for skill, details in input_data["industry"][
                                        "filter"
                                    ].items()
                                    if not details["exclusion"]
                                    and details.get("type", "").lower() == "past"
                                ]
                                if input_data["industry"]
                                and input_data.get("industry").get("event") != "OR"
                                else []
                            ),
                            "excluded": (
                                [
                                    skill
                                    for skill, details in input_data["industry"][
                                        "filter"
                                    ].items()
                                    if details["exclusion"]
                                    and details.get("type", "").lower() == "past"
                                ]
                                if input_data["industry"]
                                and input_data.get("industry").get("event") != "OR"
                                else []
                            ),
                        },
                        "both": {
                            "included": (
                                [
                                    skill
                                    for skill, details in input_data["industry"][
                                        "filter"
                                    ].items()
                                    if not details["exclusion"]
                                    and (
                                        details.get("type", "").lower() == "both"
                                        or input_data.get("industry").get("event")
                                        == "OR"
                                    )
                                ]
                                if input_data["industry"]
                                else []
                            ),
                            "excluded": (
                                [
                                    skill
                                    for skill, details in input_data["industry"][
                                        "filter"
                                    ].items()
                                    if details["exclusion"]
                                    and (
                                        details.get("type", "").lower() == "both"
                                        or input_data.get("industry").get("event")
                                        == "OR"
                                    )
                                ]
                                if input_data["industry"]
                                else []
                            ),
                        },
                    },
                }
            elif entity == "location":
                output_data = {
                    "locations": {
                        "Current": (
                            [
                                location
                                for location, details in input_data["location"][
                                    "filter"
                                ].items()
                                if details["type"] == "CURRENT"
                            ]
                            if input_data["location"]
                            and input_data.get("location").get("event") != "OR"
                            else []
                        ),
                        "Past": (
                            [
                                location
                                for location, details in input_data["location"][
                                    "filter"
                                ].items()
                                if details["type"] == "PAST"
                            ]
                            if input_data["location"]
                            and input_data.get("location").get("event") != "OR"
                            else []
                        ),
                        "Both": (
                            [
                                location
                                for location, details in input_data["location"][
                                    "filter"
                                ].items()
                                if details["type"] == "BOTH"
                                or input_data.get("location").get("event") == "OR"
                            ]
                            if input_data["location"]
                            else []
                        ),
                        "Event": (
                            input_data["location"]["event"]
                            if input_data["location"]
                            else None
                        ),
                    }
                }
            elif entity == "totalYears":
                output_data = {
                    "total_working_years": (
                        {
                            "min": (
                                input_data["experience"]["min"]
                                if "experience" in input_data
                                and "min" in input_data["experience"]
                                else None
                            ),
                            "max": (
                                input_data["experience"]["max"]
                                if "experience" in input_data
                                and "max" in input_data["experience"]
                                else None
                            ),
                        }
                        if "experience" in input_data and input_data["experience"]
                        else {"min": None, "max": None}
                    ),
                    "company_tenure": (
                        {
                            "min": (
                                input_data["company_tenure"]["min"]
                                if "company_tenure" in input_data
                                and "min" in input_data["company_tenure"]
                                else None
                            ),
                            "max": (
                                input_data["company_tenure"]["max"]
                                if "company_tenure" in input_data
                                and "max" in input_data["company_tenure"]
                                else None
                            ),
                        }
                        if "company_tenure" in input_data
                        and input_data["company_tenure"]
                        else {"min": None, "max": None}
                    ),
                    "role_tenure": (
                        {
                            "min": (
                                input_data["role_tenure"]["min"]
                                if "role_tenure" in input_data
                                and "min" in input_data["role_tenure"]
                                else None
                            ),
                            "max": (
                                input_data["role_tenure"]["max"]
                                if "role_tenure" in input_data
                                and "max" in input_data["role_tenure"]
                                else None
                            ),
                        }
                        if "role_tenure" in input_data and input_data["role_tenure"]
                        else {"min": None, "max": None}
                    ),
                }
            elif entity == "educName":
                output_data = {
                    "school": input_data.get("school", []),
                    "education": input_data.get("education", []),
                    "name": input_data["name"],
                }
                if output_data["education"]:
                    for i in output_data["education"]:
                        if "degree" in i and i["degree"]:
                            i["degree"] = i["degree"].replace("’", "").capitalize()
                        if "major" in i and i["major"]:
                            i["major"] = i["major"].replace("’", "").title()
            elif entity == "demographics":
                output_data = {
                    "ethnicity": input_data.get("ethnicity", []),
                    "gender": input_data.get("gender", []),
                    "age": input_data.get("age", []),
                }
            elif entity == "ownership":
                output_data = {"ownership": input_data.get("ownership", [])}

            all_results.append(output_data)
            all_old_prompts.append(old_prompt)

        all_old_prompts.append(new_prompt)
        results = await format_results(all_old_prompts, all_results, entity)

        results = clean_results(results)
        all_results_appended = reverse_output_to_input(results)
        if return_entity:
            return all_results_appended, entity
        return all_results_appended

    elif entity == "companyProduct":
        complete = []
        companies_dict = {}
        products_dict = {}
        for data in major_data:
            input_data = data["result"]
            old_prompt = data["prompt"]
            final = {}

            companies = input_data.get("companies")
            output_data = {"current": [], "past": []}
            current_shorten_prompt = ""
            for whole_obj in companies.get("current", {}):
                for obj in whole_obj.get("pills", []):
                    temp = {"state": obj["state"], "name": obj["name"]}
                    companies_dict[obj["name"]] = {
                        "name": obj.get("name"),
                        "id": obj.get("id"),
                        "universalName": obj.get("universalName"),
                        "urn": obj.get("urn"),
                        "industry": obj.get("industry"),
                        "employCount": obj.get("employCount"),
                    }
                    companies_dict[obj["name"]] = {
                        key: value for key, value in companies_dict[obj["name"]].items()
                    }
                    output_data["current"].append(temp)
                current_shorten_prompt += whole_obj.get("prompt", "")
            output_data["current_shorten_prompt"] = current_shorten_prompt

            past_shorten_prompt = ""
            for whole_obj in companies.get("past", {}):
                for obj in whole_obj.get("pills", []):
                    temp = {"state": obj["state"], "name": obj["name"]}
                    companies_dict[obj["name"]] = {
                        "name": obj.get("name"),
                        "id": obj.get("id"),
                        "universalName": obj.get("universalName"),
                        "urn": obj.get("urn"),
                        "industry": obj.get("industry"),
                        "employCount": obj.get("employCount"),
                    }
                    companies_dict[obj["name"]] = {
                        key: value for key, value in companies_dict[obj["name"]].items()
                    }
                    output_data["past"].append(temp)
                past_shorten_prompt += whole_obj.get("prompt", "")
            output_data["past_shorten_prompt"] = past_shorten_prompt
            output_data["event"] = companies.get("event", "")
            if output_data["event"] == "PAST":
                if output_data.get("current", []):
                    output_data["past"] = output_data["current"]
                    output_data["current"] = []
            final["companies"] = output_data

            products = input_data.get("products")
            output_data = {"current": [], "past": []}
            current_shorten_prompt = ""
            for whole_obj in products.get("current", {}):
                for obj in whole_obj.get("pills", []):
                    temp = {
                        "state": obj["state"],
                        "name": f"""{obj["productName"]} by {obj["companyName"]}""",
                    }
                    products_dict[
                        f"""{obj["productName"]} by {obj["companyName"]}"""
                    ] = {
                        "esId": obj.get("esId"),
                        "productName": obj.get("productName"),
                        "productId": obj.get("productId"),
                        "companyUniversalName": obj.get("companyUniversalName"),
                        "companyName": obj.get("companyName"),
                        "companyUrn": obj.get("companyUrn"),
                        "companyIndustry": obj.get("companyIndustry"),
                        "keywords": obj.get("keywords", []),
                        "pureplay": obj.get("pureplay", False),
                    }
                    products_dict[
                        f"""{obj["productName"]} by {obj["companyName"]}"""
                    ] = {
                        key: value
                        for key, value in products_dict[
                            f"""{obj["productName"]} by {obj["companyName"]}"""
                        ].items()
                        if value
                    }
                    output_data["current"].append(temp)
                current_shorten_prompt += whole_obj.get("prompt", "")
            output_data["current_shorten_prompt"] = current_shorten_prompt

            past_shorten_prompt = ""
            for whole_obj in products.get("past", {}):
                for obj in whole_obj.get("pills", []):
                    temp = {
                        "state": obj["state"],
                        "name": f"""{obj["productName"]} by {obj["companyName"]}""",
                    }
                    products_dict[
                        f"""{obj["productName"]} by {obj["companyName"]}"""
                    ] = {
                        "esId": obj.get("esId"),
                        "productName": obj.get("productName"),
                        "productId": obj.get("productId"),
                        "companyUniversalName": obj.get("companyUniversalName"),
                        "companyName": obj.get("companyName"),
                        "companyUrn": obj.get("companyUrn"),
                        "companyIndustry": obj.get("companyIndustry"),
                        "keywords": obj.get("keywords", []),
                        "pureplay": obj.get("pureplay", False),
                    }
                    products_dict[
                        f"""{obj["productName"]} by {obj["companyName"]}"""
                    ] = {
                        key: value
                        for key, value in products_dict[
                            f"""{obj["productName"]} by {obj["companyName"]}"""
                        ].items()
                        if value
                    }
                    output_data["past"].append(temp)
                past_shorten_prompt += whole_obj.get("prompt", "")
            output_data["past_shorten_prompt"] = past_shorten_prompt
            output_data["event"] = products.get("event", "")
            if output_data["event"] == "PAST":
                if output_data.get("current", []):
                    output_data["past"] = output_data["current"]
                    output_data["current"] = []

            final["products"] = output_data

            final["prompt"] = old_prompt

            complete.append(final)

        response = await company_product_service(
            new_prompt, complete, companies_dict, products_dict
        )
        if return_entity:
            return response, entity
        return response
    else:
        return {}


async def company_product_service(
    new_prompt, company_product_data, companies_dict, product_dict
):

    user_prompt = f"""
    <Older_queries>
        {company_product_data}
    </Older_queries>

    <New_Query>
        "{new_prompt}"
    </New_Query>
    """

    messages = [
        {"role": "system", "content": EVALUATE_COMPANY_PRODUCTS_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    response = await claude(messages)
    complete = {"filters": []}

    companies = response.get("company_dict", {})
    products = response.get("product_dict", {})

    if companies:
        complete["filters"].append("company")
        complete["company"] = company_product(companies, companies_dict)

    if products:
        complete["filters"].append("product")
        complete["product"] = company_product(products, product_dict, "products")
        if "companies" in complete["product"]["current"]:
            complete["product"]["current"]["products"] = complete["product"]["current"][
                "companies"
            ]
            del complete["product"]["current"]["companies"]
        if "companies" in complete["product"]["past"]:
            complete["product"]["past"]["products"] = complete["product"]["past"][
                "companies"
            ]
            del complete["product"]["past"]["companies"]

    if not complete["filters"]:
        return {}
    return complete


def company_product(companies, companies_dict, fill="companies"):
    company_final = {
        "current": {"companies": [], "rephrased_query": ""},
        "past": {"companies": [], "rephrased_query": ""},
        "event": "",
    }
    current_flag = False
    past_flag = False
    if companies.get("current", {}) and (
        companies.get("current", {}).get(fill, [])
        or companies.get("current", {}).get("rephrased_query", "")
    ):
        current_flag = True
    if companies.get("past", {}) and (
        companies.get("past", {}).get(fill, [])
        or companies.get("past", {}).get("rephrased_query", "")
    ):
        past_flag = True

    if current_flag and past_flag:
        event = companies.get("event", "")
        if event.lower() not in ["and", "or"]:
            event = "OR"
    elif current_flag:
        event = "CURRENT"
        company_final["past"] = {}
    elif past_flag:
        event = "PAST"
        company_final["past"] = {}
    else:
        event = ""
        company_final["past"] = {}
        company_final["current"] = {}
        company_final["shorten_prompt"] = ""

    if event:
        if event.lower() == "and":
            for companyname in list(
                companies.get("past", {}).get(fill, [])
            ):  # or companies.get("current", {}).get("rephrased_query", ""):
                if companies_dict.get(companyname, {}):
                    company_final["past"]["companies"].append(
                        companies_dict[companyname]
                    )
                else:
                    company_final["past"]["rephrased_query"] = (
                        companyname
                        + ", "
                        + company_final["past"].get("rephrased_query", "")
                    )

            company_final["current"]["shorten_prompt"] = companies.get(
                "current", {}
            ).get("shorten_prompt", "")
            company_final["past"]["shorten_prompt"] = companies.get("past", {}).get(
                "shorten_prompt", ""
            )
            company_final["past"]["rephrased_query"] += companies["past"].get(
                "rephrased_query", ""
            )
        else:
            for companyname in list(
                companies.get("past", {}).get(fill, [])
            ):  # or companies.get("current", {}).get("rephrased_query", ""):
                if companies_dict.get(companyname, {}):
                    company_final["current"]["companies"].append(
                        companies_dict[companyname]
                    )
                else:
                    company_final["current"]["rephrased_query"] = (
                        companyname
                        + ", "
                        + company_final["current"].get("rephrased_query", "")
                    )

            company_final["current"]["shorten_prompt"] = companies.get("prompt", "")
            company_final["current"]["rephrased_query"] += companies["past"].get(
                "rephrased_query", ""
            )

        for companyname in list(
            companies.get("current", {}).get(fill, [])
        ):  # or companies.get("current", {}).get("rephrased_query", ""):
            if companies_dict.get(companyname, {}):
                if (
                    companies_dict[companyname]
                    not in company_final["current"]["companies"]
                ):
                    company_final["current"]["companies"].append(
                        companies_dict[companyname]
                    )
            else:
                company_final["current"]["rephrased_query"] = (
                    companyname
                    + ", "
                    + company_final["current"].get("rephrased_query", "")
                )

        company_final["current"]["rephrased_query"] += companies["current"].get(
            "rephrased_query", ""
        )
        company_final["event"] = (
            event if event.lower() in ["or", "and", "current", "past"] else "OR"
        )

    return company_final
