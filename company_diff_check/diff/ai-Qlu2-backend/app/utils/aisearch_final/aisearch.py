import anthropic, asyncio

from app.utils.aisearch_final.prompts import *
import os

client = anthropic.AsyncAnthropic(
    api_key=os.getenv("ANTHROPIC_KEY"),
)


async def claude(messages, model=None, retries=3):
    if not model:
        model = "claude-3-5-sonnet-latest"
    for i in range(retries):
        try:
            message = await client.messages.create(
                model=model,
                max_tokens=8192,
                temperature=0,
                messages=messages,
            )
            response = message.content[0].text
            response = response.replace("null", "None")
            return response
        except:
            pass


def to_case_insensitive_regex(input_string):
    regex_pattern = "".join(
        f"[{char.lower()}{char.upper()}]" if char.isalpha() else char
        for char in input_string
    )
    return regex_pattern


async def verify_school(school_name, client):
    body = {
        "query": {
            "bool": {
                "should": [
                    {
                        "regexp": {
                            "name.keyword": {
                                "value": to_case_insensitive_regex(school_name)
                            }
                        }
                    }
                ]
            }
        }
    }

    response = await client.search(index="school_name", body=body)
    if len(response["hits"]["hits"]) == 0:
        return None
    return school_name


async def reverse_output_to_input(output_data, es_client, demoBlocked=False):
    main_output = {}

    levels_mapping = {
        "C-Suite/Chiefs": "C Suite",
        "President": "President",
        "Executive VP or Sr. VP": "Executive and Sr. VP",
        "Founder or Co-founder": "Founder/Co-Founder",
        "Senior (All Senior-Level Individual Contributors)": "Senior (Individual Contributor)",
        "Mid (All Mid-Level Individual Contributors)": "Mid (Individual Contributor)",
        "Junior (All Junior-Level Individual Contributors)": "Junior",
        "Senior": "Senior (Individual Contributor)",
        "Mid": "Mid (Individual Contributor)",
        "Junior": "Junior",
    }

    input_data = {}
    try:
        if "school" in output_data:
            input_data["school"] = output_data.get("school", [])
            institution = input_data["school"]
            tasks = []
            for institue in institution:
                tasks.append(verify_school(institue, es_client))
            verified_schools = await asyncio.gather(*tasks)

            output = []
            for institue in verified_schools:
                if institue:
                    output.append(institue)
            main_output["school"] = output
    except:
        print("school error")
        pass

    # Reverse education
    try:
        if "education" in output_data:
            input_data["education"] = output_data.get("education", [])
        main_output["education"] = input_data.get("education", [])
    except:
        print("education error")
        pass

    # Reverse experience
    try:
        if "experience" in output_data:
            input_data["experience"] = (
                {
                    "min": output_data["experience"][0],
                    "max": output_data["experience"][1],
                }
                if isinstance(output_data["experience"], list)
                and len(output_data["experience"]) == 2
                and (output_data["experience"][1] - output_data["experience"][0] <= 59)
                else None
            )
        main_output["experience"] = input_data.get("experience", {})
    except:
        print("experience error")
        pass

    try:
        if "company_tenure" in output_data:
            input_data["company_tenure"] = (
                {
                    "min": output_data["company_tenure"][0],
                    "max": output_data["company_tenure"][1],
                }
                if isinstance(output_data["company_tenure"], list)
                and len(output_data["company_tenure"]) == 2
                and (
                    output_data["company_tenure"][1] - output_data["company_tenure"][0]
                    <= 59
                )
                else None
            )
        main_output["company_tenure"] = input_data.get("company_tenure", {})
    except Exception as e:
        print(e)
        print("company error")
        pass

    try:
        if "role_tenure" in output_data:
            input_data["role_tenure"] = (
                {
                    "min": output_data["role_tenure"][0],
                    "max": output_data["role_tenure"][1],
                }
                if isinstance(output_data["role_tenure"], list)
                and len(output_data["role_tenure"]) == 2
                and (
                    output_data["role_tenure"][1] - output_data["role_tenure"][0] <= 59
                )
                else None
            )
        main_output["role_tenure"] = input_data.get("role_tenure", {})
    except:
        print("role error")
        pass

    try:
        if "industry" in output_data:
            raise
            common_elements = set(output_data["industry"].get("current", [])) & set(
                output_data["industry"].get("past", [])
            )
            both = output_data["industry"].get("both", [])
            both.extend(
                item
                for item in common_elements
                if item not in output_data["industry"].get("both", [])
            )
            output_data["industry"]["both"] = both

            output_data["industry"]["current"] = [
                item
                for item in output_data["industry"].get("current", [])
                if item not in common_elements
            ]
            output_data["industry"]["past"] = [
                item
                for item in output_data["industry"].get("past", [])
                if item not in common_elements
            ]

            input_data["industry"] = {"event": None, "filter": {}}
            current = output_data["industry"].get("current", [])
            past = output_data["industry"].get("past", [])

            if current and not past and not both:
                input_data["industry"]["event"] = "CURRENT"
            elif past and not current and not both:
                input_data["industry"]["event"] = "PAST"
            else:
                input_data["industry"]["event"] = next(
                    (
                        item
                        for item in ["OR", "AND"]
                        if item in output_data["industry"].get("event", "").upper()
                    ),
                    "OR",
                )

            input_data["industry"]["filter"].update(
                {
                    location: {"type": "CURRENT"}
                    for location in output_data["industry"].get("current", [])
                }
            )
            input_data["industry"]["filter"].update(
                {
                    location: {"type": "PAST"}
                    for location in output_data["industry"].get("past", [])
                }
            )
            input_data["industry"]["filter"].update(
                {
                    location: {"type": "BOTH"}
                    for location in output_data["industry"].get("both", [])
                }
            )
            main_output["industry"] = input_data.get("industry", {})
    except:
        print("industry error")
        pass
    # Reverse job_titles
    try:
        if "title" in output_data:

            common_elements = {}
            current_titles = output_data["title"].get("current", [])
            past_titles = output_data["title"].get("past", [])
            both_titles = output_data["title"].get("either", [])

            for current in current_titles:
                current_name = current.get("title_name")
                if current_name:
                    for past in past_titles:
                        if current_name == past.get("title_name"):
                            common_elements[current_name] = {
                                "title_name": current_name,
                                "min_staff": min(
                                    current.get("min_staff", float("inf")),
                                    past.get("min_staff", float("inf")),
                                ),
                                "max_staff": max(
                                    current.get("max_staff", float("-inf")),
                                    past.get("max_staff", float("-inf")),
                                ),
                            }

            both_names = {item.get("title_name") for item in both_titles}
            for common in common_elements.values():
                if common["title_name"] not in both_names:
                    both_titles.append(common)

            output_data["title"]["current"] = [
                item
                for item in current_titles
                if item.get("title_name") not in common_elements
            ]

            output_data["title"]["past"] = [
                item
                for item in past_titles
                if item.get("title_name") not in common_elements
            ]

            output_data["title"]["either"] = both_titles

            current = output_data["title"].get("current", [])
            past = output_data["title"].get("past", [])
            both = both_titles

            input_data["title"] = {"event": None, "filter": {}}
            if current and not past and not both:
                input_data["title"]["event"] = "CURRENT"
            elif past and not current and not both:
                input_data["title"]["event"] = "PAST"
            else:
                input_data["title"]["event"] = next(
                    (
                        item
                        for item in ["OR", "AND"]
                        if item in output_data["title"].get("event", "").upper()
                    ),
                    "OR",
                )

            input_data["title"]["filter"].update(
                {
                    title["title_name"]: {
                        "min": title["min_staff"],
                        "max": title["max_staff"],
                        "type": "CURRENT",
                    }
                    for title in output_data["title"].get("current", [])
                }
            )
            input_data["title"]["filter"].update(
                {
                    title["title_name"]: {
                        "min": title["min_staff"],
                        "max": title["max_staff"],
                        "type": "PAST",
                    }
                    for title in output_data["title"].get("past", [])
                }
            )
            input_data["title"]["filter"].update(
                {
                    title["title_name"]: {
                        "min": title["min_staff"],
                        "max": title["max_staff"],
                        "type": "BOTH",
                    }
                    for title in output_data["title"].get("either", [])
                }
            )
        main_output["title"] = input_data.get("title", {})
    except:
        print("title error")
        pass
    # Reverse management_levels
    try:
        if "management_level" in output_data:
            possible_levels = [
                "Partners",
                "Founder/Co-Founder",
                "Board of Directors",
                "C Suite",
                "President",
                "Executive and Sr. VP",
                "VP",
                "Director",
                "Manager",
                "Senior (Individual Contributor)",
                "Mid (Individual Contributor)",
                "Junior",
                "Head",
            ]

            common_elements = set(
                output_data["management_level"].get("current", [])
            ) & set(output_data["management_level"].get("past", []))
            both = output_data["management_level"].get("either", [])
            both.extend(
                item
                for item in common_elements
                if item not in output_data["management_level"].get("either", [])
            )
            output_data["management_level"]["either"] = both

            output_data["management_level"]["current"] = [
                item
                for item in output_data["management_level"].get("current", [])
                if item not in common_elements
            ]
            output_data["management_level"]["past"] = [
                item
                for item in output_data["management_level"].get("past", [])
                if item not in common_elements
            ]

            current = [
                item for item in output_data["management_level"].get("current", [])
            ]
            past = [item for item in output_data["management_level"].get("past", [])]
            both = [item for item in output_data["management_level"].get("either", [])]

            input_data["management_level"] = {"event": None}

            if current and not past and not both:
                input_data["management_level"]["event"] = "CURRENT"
            elif past and not current and not both:
                input_data["management_level"]["event"] = "PAST"
            else:
                input_data["management_level"]["event"] = next(
                    (
                        item
                        for item in ["OR", "AND"]
                        if item
                        in output_data["management_level"].get("event", "").upper()
                    ),
                    "OR",
                )

            input_data["management_level"]["filter"] = {
                levels_mapping.get(level, level): {"type": "CURRENT"}
                for level in output_data["management_level"].get("current", [])
                if levels_mapping.get(level, level) in possible_levels
            }

            input_data["management_level"]["filter"].update(
                {
                    levels_mapping.get(level, level): {"type": "PAST"}
                    for level in output_data["management_level"].get("past", [])
                    if levels_mapping.get(level, level) in possible_levels
                }
            )
            input_data["management_level"]["filter"].update(
                {
                    levels_mapping.get(level, level): {"type": "BOTH"}
                    for level in output_data["management_level"].get("either", [])
                    if levels_mapping.get(level, level) in possible_levels
                }
            )
        main_output["management_level"] = input_data.get("management_level", {})
    except Exception as e:
        print("level error")
        pass
    # Reverse skills
    try:
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
        main_output["skill"] = (
            input_data.get("skill", {})
            if input_data.get("skill", {}).get("filter", {})
            else {}
        )
    except:
        print("skill error")
        pass

    try:
        if "location" in output_data:

            common_elements = set(output_data["location"].get("current", [])) & set(
                output_data["location"].get("past", [])
            )
            both = output_data["location"].get("either", [])
            both.extend(
                item
                for item in common_elements
                if item not in output_data["location"].get("either", [])
            )
            output_data["location"]["either"] = both

            output_data["location"]["current"] = [
                item
                for item in output_data["location"].get("current", [])
                if item not in common_elements
            ]
            output_data["location"]["past"] = [
                item
                for item in output_data["location"].get("past", [])
                if item not in common_elements
            ]

            for timeline in ["current", "either", "past"]:
                if "South America" in output_data["location"].get(timeline, []):
                    output_data["location"].get(timeline, []).extend(
                        [
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
                        ]
                    )
                if "North America" in output_data["location"].get(timeline, []):
                    output_data["location"].get(timeline, []).extend(
                        [
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
                        ]
                    )
                if "Oceania" in output_data["location"].get(timeline, []):
                    output_data["location"].get(timeline, []).extend(
                        [
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
                        ]
                    )

            input_data["location"] = {"event": None, "filter": {}}
            current = output_data["location"].get("current", [])
            past = output_data["location"].get("past", [])

            if current and not past and not both:
                input_data["location"]["event"] = "CURRENT"
            elif past and not current and not both:
                input_data["location"]["event"] = "PAST"
            else:
                input_data["location"]["event"] = next(
                    (
                        item
                        for item in ["OR", "AND"]
                        if item in output_data["location"].get("event", "").upper()
                    ),
                    "OR",
                )

            input_data["location"]["filter"].update(
                {
                    location: {"type": "CURRENT"}
                    for location in output_data["location"].get("current", [])
                }
            )
            input_data["location"]["filter"].update(
                {
                    location: {"type": "PAST"}
                    for location in output_data["location"].get("past", [])
                }
            )
            input_data["location"]["filter"].update(
                {
                    location: {"type": "BOTH"}
                    for location in output_data["location"].get("either", [])
                }
            )
        main_output["location"] = input_data.get("location", {})
    except:
        print("location error")
        pass
    # Reverse names

    try:
        if "name" in output_data:
            input_data["name"] = output_data.get("name", [])
        main_output["name"] = input_data.get("name", [])
    except:
        print("name error")
        pass

    if not demoBlocked:
        try:
            if "age" in output_data:
                input_data["age"] = [
                    item
                    for item in output_data.get("age", [])
                    if item in ["Under 25", "Over 50", "Over 65"]
                ]
            main_output["age"] = input_data.get("age", [])
        except:
            print("age error")
            pass

        try:
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
            main_output["gender"] = input_data.get("gender", [])
        except:
            print("gender error")
            pass

        try:
            if "ethnicity" in output_data:
                input_data["ethnicity"] = [
                    item
                    for item in output_data.get("ethnicity", [])
                    if item
                    in [
                        "Asian",
                        "African",
                        "Hispanic",
                        "Middle Eastern",
                        "South East Asian",
                        "South Asian",
                    ]
                ]
                if "Black" in input_data["ethnicity"]:
                    input_data["ethnicity"].remove("Black")
                    input_data["ethnicity"].append("African")
                if "South East Asian" in input_data["ethnicity"]:
                    input_data["ethnicity"].remove("South East Asian")
                    if "South Asian" not in input_data["ethnicity"]:
                        input_data["ethnicity"].append("South Asian")
            main_output["ethnicity"] = input_data.get("ethnicity", [])
        except:
            print("ethnicity error")
            pass

    try:
        input_data["ownership"] = [
            item
            for item in output_data.get("current_companys_ownership", [])
            if item in ["Public", "Private", "VC Funded", "Private Equity Backed"]
        ]
        main_output["ownership"] = input_data.get("ownership", [])
    except:
        print("ownership error")
        pass

    main_output = {key: value for key, value in main_output.items() if value}
    return main_output


def clean_results(data):

    key_mapping = {
        "total_working_years": "experience",
        "job_title": "title",
        "management_levels": "management_level",
        "skills": "skill",
        "locations": "location",
        "names": "name",
        "isExperienceSelected": "isExperienceSelected",  # Key added as requested
    }

    for key in ["job_title", "management_level", "location", "industry"]:
        if key in data and all(
            not data[key][k] for k in ["current", "past", "either"] if k in data[key]
        ):
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
    #     for timeline in ["current", "past", "both"]:
    #         if timeline in data["management_levels"] and data["management_levels"].get(
    #             timeline, []
    #         ):
    #             for level in list(data["management_levels"][timeline]):
    #                 if level not in possible_levels:
    #                     if "job_titles" not in data:
    #                         data["job_titles"] = {"current": [], "past": [], "both": []}

    #                     if timeline not in data["job_titles"] or data["job_titles"].get(
    #                         timeline, []
    #                     ):
    #                         data["job_titles"][timeline] = []

    #                     data["job_titles"][timeline].append({"name" : level, "min" :300})

    #                     data["management_levels"][timeline].remove(level)

    if "skill" in data and not data["skill"]:
        del data["skill"]

    for key in ["school", "education", "name"]:
        try:
            if key in data and not data[key]:
                del data[key]
            elif key in data and key == "education":
                if isinstance(data[key], dict):
                    data[key] = [data[key]]
                for index in range(len(data[key])):
                    if (
                        "degree" in data[key][index]
                        and data[key][index].get("degree")
                        and any(
                            item in data[key][index].get("degree")
                            for item in [
                                "Associate",
                                "Bachelor's",
                                "Master's",
                                "Doctorate",
                                "Diploma",
                                "Certificate",
                            ]
                        )
                    ):
                        for any_item in [
                            "Associate",
                            "Bachelor's",
                            "Master's",
                            "Doctorate",
                            "Diploma",
                            "Certificate",
                        ]:
                            if any_item in data[key][index].get("degree"):
                                data[key][index]["degree"] = (
                                    any_item.replace("Bachelor's", "Bachelor’s")
                                    .replace("Master's", "Master’s")
                                    .capitalize()
                                    .strip()
                                )
                                break

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
        except:
            del data[key]

    if "total_working_years" in data and (
        data["total_working_years"] == {"min": None, "max": None}
        or data["total_working_years"] == {"min": -1, "max": 60}
        or data["total_working_years"] == [0, 60]
    ):
        del data["total_working_years"]

    if "role_tenure" in data and (
        data["role_tenure"] == {"min": None, "max": None}
        or data["role_tenure"] == {"min": 0, "max": 60}
        or data["role_tenure"] == [0, 60]
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
        or data["company_tenure"] == [0, 60]
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


def has_meaningful_letters(query):
    # Count letters that are actual alphabetic characters
    letter_count = sum(1 for char in query if char.isalpha())
    return letter_count >= 3


async def main(query, es_client, demoBlocked=False, return_type=False):

    EXTRACT_USER_PROMPT = (
        EXTRACT_USER_PROMPT_1
        + (EXTRACT_USER_PROMPT_DEMO if not demoBlocked else "")
        + EXTRACT_USER_PROMPT_2
    )
    retries = 3
    for index in range(retries):
        try:
            if not has_meaningful_letters(query):
                return {}

            user_checking_prompt = (
                f"""{COMPANY_PRODUCTS_ONLY}\n\n<Query>\n{query}\n</Query>\n"""
            )

            checking_messages = [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": user_checking_prompt}],
                }
            ]

            user_prompt = f"""Great! Here is the user query:\n\n\'''{query}'''\n\nFor each filter, first give your reasoning and then your output (ALWAYS a json object enclosed within <Output></Output> tags).\nThink logically about what the user requires, without decreasing the recall or precision, and apply filters and their current, past, and, or according to what would bring the best results to the user."""

            if index == 1:
                user_prompt = (
                    user_prompt
                    + " Be very mindful of the output formats above, for each filter and for the whole output."
                )
            messages = [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": EXTRACT_USER_PROMPT}],
                },
                {"role": "assistant", "content": [{"type": "text", "text": "YES."}]},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": user_prompt,
                        }
                    ],
                },
            ]
            response, checker = await asyncio.gather(
                *[
                    claude(messages),
                    claude(checking_messages),
                ]
            )
            try:
                checker = (
                    checker[checker.rfind("<Output>") : checker.rfind("</Output>")]
                    .replace("<Output>", "")
                    .replace("<", "")
                )
                checker = eval(checker.strip())
                if checker.get("only_company_products", 0):
                    if return_type:
                        return {}, "filters"
                    return {}
            except Exception as e:
                pass

            # messages.append(
            #     {"role": "assistant", "content": [{"type": "text", "text": response}]}
            # )

            # messages.append(
            #     {"role": "user", "content": [{"type": "text", "text": MODIFY_USER_PROMPT}]}
            # )

            # response = await claude(messages)

            response = (
                response[response.rfind("<Output>") : response.rfind("</Output>")]
                .replace("<Output>", "")
                .replace("<", "")
            )
            results = eval(response.strip())
            results = clean_results(results)
            all_results_appended = await reverse_output_to_input(
                results, es_client, demoBlocked
            )
            if return_type:
                return all_results_appended, "filters"
            return all_results_appended
        except:
            pass

    if return_type:
        return {}, "filters"
    return {}
