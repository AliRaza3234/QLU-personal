import asyncio
import traceback
from numpy import mean
import requests
import os

from utils import call_comp_gen_endpoint, get_profiles_from_es, extract_generic
from es_query import create_search_payload
from qutils.llm.utilities import asynchronous_llm
from qutils.qes.es_utils import make_es_connection

MAP_TIMELINE = {
    "CURRENT": "Current",
    "PAST": "Past",
    "OR": "Current or Past",
    "AND": "Current and Past",
    "CURRENT OR PAST": "Current or Past",
    "CURRENT AND PAST": "Current and Past",
}

MAP_MANAGEMENT_LEVELS = {
    "Senior (Individual Contributor)": "Senior (Individual contributor)",
    "Mid (Individual Contributor)": "Mid (Individual contributor)",
}

async def create_criteria(query: str):
    system = """<role> You breakdown user queries and generate a proper marking scheme to be used by evaluators </role>"""

    user = f"""<instructions>
- Understand all parts of the user query 
- Output all distinct criteria that a singular profile should meet according to the query
- The criteria should be something the query mentions explicitly, you cannot ever change the requirements yourself
- Assign a weightage to each criteria
- The weightage will be indicative of the importance of each criteria according the user query
- If you think the query is putting emphasis on a certain criteria then it will have a greater weightage
- The sum of weightages across all criterias should be 100
</instructions>

<output format>
Output each criteria as a string with its corresponding weightage in the following xml format
<criteria1>
criteria in a paragraph or line
</criteria1>
<weightage1>
weightage for criteria 1
</weightage1>
<criteria2>
...
</output format>

<user query>
{query}
</user query>"""
    
    res = await asynchronous_llm(messages=[
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ], temperature=0, model="claude-3-7-latest", provider="anthropic")

    return res

def format_profile_data_complete(
    profiles, profile_experience_hits: dict[str, list[int]]
):
    formatted_profile_data = []
    count = 0

    for profile_data in profiles:
        count += 1

        profile_id = profile_data["_id"]
        profile_summary = profile_data["_source"]["summary"]
        profile_skills = profile_data["_source"]["skills"]
        profile_location = profile_data["_source"]["location_full_path"]
        experience_array = profile_data["_source"]["experience"]
        education_array = profile_data["_source"]["education"]
        total_tenure = profile_data["_source"].get("total_tenure", None)
        if total_tenure:
            total_tenure = round(total_tenure/365, 2)
        
        relevant_experiences = []
        other_experiences = []
        
        for experience in experience_array:
            if "index" not in experience:
                print(f"Profile without index in experience = {profile_id}")
                continue
            if experience["index"] in profile_experience_hits[profile_id]:
                relevant_experiences.append(experience)
            else:
                other_experiences.append(experience)

        relevant_companies = []
        _set = set()

        relevant_experience_string = []
        for experience in relevant_experiences:
            start_date = experience["start"]
            end_date = experience["end"]
            title = experience["title"]
            experience_location = experience["location"]
            job_summary = experience["job_summary"]

            company_name = experience["company"]
            company_industry = experience["company_industry"]
            company_specialties = experience["company_speciality"]
            company_description = experience["company_description"]

            company_size = experience["company_size"]

            if isinstance(company_industry, str):
                company_industry = [company_industry]

            if isinstance(company_specialties, str):
                company_specialties = [company_specialties]

            if not company_industry:
                company_industry = []
                
            if not company_specialties:
                company_specialties = []

            company_industry = list(set(company_industry + company_specialties))

            if experience["company_urn"] not in _set:
                temp = []
                if company_description:
                    temp.append(company_description)
                if company_industry:
                    temp.append(f"Industries: {company_industry}")
                if company_size:
                    temp.append(f"Company size: {company_size}")

                temp = "\n".join(temp)

                if temp:
                    temp = f"<{company_name}>\n{temp}\n</{company_name}>"
                
                relevant_companies.append(temp)
                _set.add(experience["company_urn"])

            if not end_date:
                end_date = "Now"
            else:
                end_date = end_date.split("-")[0]

            if not start_date:
                start_date = "Unknown"
            else:
                start_date = start_date.split("-")[0]

            temp = f"{title} at {company_name}\n{start_date} - {end_date}"

            if experience_location:
                temp += f"\nLocation: {experience_location}"
            
            if job_summary:
                temp += f"\n{job_summary}"

            relevant_experience_string.append(temp)

        other_experience_string = []

        education_string=[]
        if education_array:
            for education_item in education_array:
                degree = education_item.get("degree", None)
                major = education_item.get("major", None)
                school = education_item.get("school", None)
                
                temp = f"{degree}"
                if major:
                    temp += f" in {major}"
                
                if school:
                    temp += f" from {school}"

                education_string.append(temp)

        education_string = "\n".join(education_string)
        relevant_experience_string = "\n\n".join(relevant_experience_string)
        other_experience_string = "\n\n".join(other_experience_string)
        relevant_companies = "\n".join(relevant_companies)

        profile_string = []

        about_section = []
        if profile_summary:
            about_section.append(profile_summary)
        if profile_skills:
            about_section.append(f"Profile skills: {profile_skills}")
        if total_tenure:
            about_section.append(f"Total Working Experience: {total_tenure}")
        if profile_location:
            about_section.append(f"\nProfile Location = {profile_location}")

        if about_section:
            about_section = "<about>\n" + "\n".join(about_section) + "\n</about>"
            profile_string.append(about_section)

        if relevant_experience_string:
            relevant_experience_string = f"<relevant experiences>\n{relevant_experience_string}\n</relevant experiences>"
            profile_string.append(relevant_experience_string)

        if other_experience_string:
            other_experience_string = f"<other experiences>\n{other_experience_string}\n</other experiences>"
            profile_string.append(other_experience_string)

        if relevant_companies:
            profile_string.append(f"<companies>\n{relevant_companies}\n</companies>") 
        
        if education_string:
            profile_string.append(f"\n<education>\n{education_string}\n</education>")

        profile_string = "\n".join(profile_string)
        
        formatted_profile_data.append(f"<profile_data>\n{profile_string}\n</profile_data>")

    return formatted_profile_data

def sample_ids(ids: list):
    if len(ids) <= 15:
        return ids
    
    start_5 = ids[:5]
    end_5 = ids[-5:]
    
    mid_5 = ids[len(ids)//2 - 2 : len(ids)//2 + 3]

    return list(set(start_5 + end_5 + mid_5))

def clean_results(data):

    key_mapping = {
        "total_working_years": "experience",
        "job_title": "title",
        "job_title/business_function": "title",
        "management_levels": "management_level",
        "company_keywords": "industry",
        "profile_keywords": "skill",
        "locations": "location",
        "names": "name",
        "isExperienceSelected": "isExperienceSelected",  # Key added as requested
    }

    for key in ["job_title", "management_level", "location", "industry"]:
        if key in data and all(
            not data[key][k] for k in ["current", "past", "both"] if k in data[key]
        ):
            del data[key]

    if "company" in data and not data["company"]:
        del data["company"]
    elif "company" in data and (
        not data["company"].get("current_prompt", None)
        and not data["company"].get("past_prompt", None)
    ):
        del data["company"]

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
                        and data[key][index].get("degree")
                        in [
                            "Associate",
                            "Bachelor's",
                            "Master's",
                            "Doctorate",
                            "Diploma",
                            "Certificate",
                        ]
                    ):
                        data[key][index]["degree"] = (
                            data[key][index]["degree"]
                            .replace("Bachelor's", "Bachelor’s")
                            .replace("Master's", "Master’s")
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


async def reverse_output_to_input(output_data):
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
            # institution = input_data["school"]
            # tasks = []
            # for institue in institution:
            #     tasks.append(verify_school(institue, es_client))
            # verified_schools = await asyncio.gather(*tasks)

            # output = []
            # for institue in verified_schools:
            #     if institue:
            #         output.append(institue)
            main_output["school"] = input_data["school"]
    except:
        print("school error")
        pass

    try:
        if "company" in output_data:
            input_data["company"] = output_data.get("company", {})
            main_output["company"] = input_data["company"]
    except:
        print("company error")
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
                    "min": output_data["experience"]["min"],
                    "max": output_data["experience"]["max"],
                }
                if isinstance(output_data["experience"], dict)
                and len(output_data["experience"]) == 2
                and (
                    output_data["experience"]["max"] - output_data["experience"]["min"]
                    <= 59
                )
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
                    "min": output_data["company_tenure"]["min"],
                    "max": output_data["company_tenure"]["max"],
                }
                if isinstance(output_data["company_tenure"], dict)
                and len(output_data["company_tenure"]) == 2
                and (
                    output_data["company_tenure"]["max"]
                    - output_data["company_tenure"]["min"]
                    <= 59
                )
                else None
            )
        main_output["company_tenure"] = input_data.get("company_tenure", {})
    except Exception as e:
        print(e)
        print("company tenure error")
        pass

    try:
        if "role_tenure" in output_data:
            input_data["role_tenure"] = (
                {
                    "min": output_data["role_tenure"]["min"],
                    "max": output_data["role_tenure"]["max"],
                }
                if isinstance(output_data["role_tenure"], dict)
                and len(output_data["role_tenure"]) == 2
                and (
                    output_data["role_tenure"]["max"]
                    - output_data["role_tenure"]["min"]
                    <= 59
                )
                else None
            )
        main_output["role_tenure"] = input_data.get("role_tenure", {})
    except:
        print("role tenure error")
        pass

    try:
        if "industry" in output_data:

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
            both_titles = output_data["title"].get("both", [])

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

            output_data["title"]["both"] = both_titles

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
                    for title in output_data["title"].get("both", [])
                }
            )
        main_output["title"] = input_data.get("title", {})
    except Exception as e:
        print("title error")
        print(output_data["title"])
        raise e
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
            both = output_data["management_level"].get("both", [])
            both.extend(
                item
                for item in common_elements
                if item not in output_data["management_level"].get("both", [])
            )
            output_data["management_level"]["both"] = both

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
            both = [item for item in output_data["management_level"].get("both", [])]

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
                    for level in output_data["management_level"].get("both", [])
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
                    "relation": "OR",
                    "filter": {
                        skill: {"exclusion": False, "type": "CURRENT"}
                        for skill in output_data["skill"]
                    },
                }
                if output_data["skill"]
                else {}
            )
        main_output["skill"] = input_data.get("skill", {})
    except:
        print("skill error")
        pass

    try:
        if "location" in output_data:

            common_elements = set(output_data["location"].get("current", [])) & set(
                output_data["location"].get("past", [])
            )
            both = output_data["location"].get("both", [])
            both.extend(
                item
                for item in common_elements
                if item not in output_data["location"].get("both", [])
            )
            output_data["location"]["both"] = both

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

            for timeline in ["current", "both", "past"]:
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
                    for location in output_data["location"].get("both", [])
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
            for item in output_data.get("current_ownership", [])
            if item in ["Public", "Private", "VC Funded", "Private Equity Backed"]
        ]
        main_output["ownership"] = input_data.get("ownership", [])
    except:
        print("ownership error")
        pass

    main_output = {key: value for key, value in main_output.items() if value}
    return main_output


async def process_approaches(approaches: list):
    processed_approaches = []
    comp_gen_tasks = []
    comp_gen_indexes = []
    comp_gen_timelines = []

    for idx, approach in enumerate(approaches):
        filters = {}
        for filter, filter_values in approach.items():

            if filter == "title" and filter_values["filter"]:
                filters["job_titles_timeline"] = MAP_TIMELINE[filter_values["event"]]
                job_titles = {"current": {}, "previous": {}}

                for title, title_attributes in filter_values["filter"].items():
                    if (
                        title_attributes["type"] == "CURRENT"
                        or title_attributes["type"] == "OR"
                    ):
                        job_titles["current"][title] = (
                            title_attributes["min"],
                            title_attributes["max"],
                        )
                    elif title_attributes["type"] == "PAST":
                        job_titles["previous"][title] = (
                            title_attributes["min"],
                            title_attributes["max"],
                        )
                    elif (
                        title_attributes["type"] == "AND"
                        or title_attributes["type"] == "BOTH"
                    ):
                        job_titles["previous"][title] = (
                            title_attributes["min"],
                            title_attributes["max"],
                        )
                        job_titles["current"][title] = (
                            title_attributes["min"],
                            title_attributes["max"],
                        )
                    else:
                        raise Exception(
                            f"Invalid job title timeline = {title_attributes['type']}"
                        )

                filters["job_titles"] = job_titles

            elif filter == "skill" and filter_values["filter"]:
                filters["skills_timeline"] = MAP_TIMELINE[filter_values["event"]]

                skills = {"current": [], "previous": []}

                for skill, skill_attributes in filter_values["filter"].items():

                    if (
                        skill_attributes["type"] == "CURRENT"
                        or skill_attributes["type"] == "OR"
                    ):
                        skills["current"].append(skill)

                    elif skill_attributes["type"] == "PAST":
                        skills["previous"].append(skill)

                    elif (
                        skill_attributes["type"] == "AND"
                        or skill_attributes["type"] == "BOTH"
                    ):
                        skills["previous"].append(skill)
                        skills["current"].append(skill)

                    else:
                        raise Exception(
                            f"Invalid skills timeline = {skill_attributes['type']}"
                        )

                filters["skills"] = skills

            elif filter == "management_level" and filter_values["filter"]:
                filters["management_levels_timeline"] = MAP_TIMELINE[
                    filter_values["event"]
                ]

                management_levels = {"current": [], "previous": []}

                for management_level, management_level_attributes in filter_values[
                    "filter"
                ].items():
                    management_level = MAP_MANAGEMENT_LEVELS.get(
                        management_level, management_level
                    )

                    if (
                        management_level_attributes["type"] == "CURRENT"
                        or management_level_attributes["type"] == "OR"
                    ):
                        management_levels["current"].append(management_level)

                    elif management_level_attributes["type"] == "PAST":
                        management_levels["previous"].append(management_level)

                    elif (
                        management_level_attributes["type"] == "AND"
                        or management_level_attributes["type"] == "BOTH"
                    ):
                        management_levels["previous"].append(management_level)
                        management_levels["current"].append(management_level)

                    else:
                        raise Exception(
                            f"Invalid magamenet level timeline = {management_level_attributes['type']}"
                        )

                filters["management_levels"] = management_levels

            elif filter == "location" and filter_values["filter"]:
                filters["locations_timeline"] = MAP_TIMELINE[filter_values["event"]]

                locations = {"current": [], "previous": []}

                for location, location_attributes in filter_values["filter"].items():

                    if (
                        location_attributes["type"] == "CURRENT"
                        or location_attributes["type"] == "OR"
                    ):
                        locations["current"].append(location)

                    elif location_attributes["type"] == "PAST":
                        locations["previous"].append(location)

                    elif (
                        location_attributes["type"] == "AND"
                        or location_attributes["type"] == "BOTH"
                    ):
                        locations["previous"].append(location)
                        locations["current"].append(location)

                    else:
                        raise Exception(
                            f"Invalid location timeline = {location_attributes['type']}"
                        )

                filters["locations"] = locations

            elif filter == "industry" and filter_values["filter"]:
                filters["industries_timeline"] = MAP_TIMELINE[filter_values["event"]]

                industries = {"current": [], "previous": []}

                for industry, industry_attributes in filter_values["filter"].items():

                    if (
                        industry_attributes["type"] == "CURRENT"
                        or industry_attributes["type"] == "OR"
                    ):
                        industries["current"].append(industry)

                    elif industry_attributes["type"] == "PAST":
                        industries["previous"].append(industry)

                    elif (
                        industry_attributes["type"] == "AND"
                        or industry_attributes["type"] == "BOTH"
                    ):
                        industries["previous"].append(industry)
                        industries["current"].append(industry)

                    else:
                        raise Exception(
                            f"Invalid industry timeline = {industry_attributes['type']}"
                        )

                filters["industries"] = industries

            elif filter == "role_tenure" and filter_values:

                min_role_tenure, max_role_tenure = filter_values.get(
                    "min", None
                ), filter_values.get("max", None)
                if min_role_tenure:
                    filters["role_tenure_min"] = min_role_tenure

                if max_role_tenure:
                    filters["role_tenure_max"] = max_role_tenure

                filters["is_role_tenure_selected"] = True

            elif filter == "experience" and filter_values:

                min_experience, max_experience = filter_values.get(
                    "min", None
                ), filter_values.get("max", None)
                if min_experience:
                    filters["experience_min"] = min_experience

                if max_experience:
                    filters["experience_max"] = max_experience

                filters["is_experience_selected"] = True

            elif filter == "company_tenure" and filter_values:

                min_company_tenure, max_company_tenure = filter_values.get(
                    "min", None
                ), filter_values.get("max", None)
                if min_company_tenure:
                    filters["company_tenure_min"] = min_company_tenure

                if max_company_tenure:
                    filters["company_tenure_max"] = max_company_tenure

                filters["is_company_tenure_selected"] = True

            elif filter == "company":
                current_prompt = filter_values.get("current_prompt", "")
                past_prompt = filter_values.get("past_prompt", "")
                timeline = MAP_TIMELINE[filter_values["event"]]

                comp_gen_indexes.append(idx)
                comp_gen_timelines.append(timeline)
                comp_gen_tasks.append(
                    call_comp_gen_endpoint(current_prompt, past_prompt)
                )

            elif filter == "education":
                education_array = filter_values
                filters["education"] = education_array

            elif filter == "school":
                filters["university"] = filter_values

        processed_approaches.append(filters)

    comp_gen_res = await asyncio.gather(*comp_gen_tasks)

    for idx, (current_companies, previous_companies) in enumerate(comp_gen_res):
        approach_index = comp_gen_indexes[idx]

        current_companies = [
            {
                "id": company["es_data"]["es_id"],
                "name": company["es_data"]["name"],
                "industry": company["es_data"]["industry"],
                "universalName": company["es_data"]["universalName"],
                "urn": company["es_data"]["urn"],
                "logo": "",
            }
            for company in current_companies
        ]

        previous_companies = [
            {
                "id": company["es_data"]["es_id"],
                "name": company["es_data"]["name"],
                "industry": company["es_data"]["industry"],
                "universalName": company["es_data"]["universalName"],
                "urn": company["es_data"]["urn"],
                "logo": "",
            }
            for company in previous_companies
        ]

        companies_object = {
            "companies": {"current": current_companies, "previous": previous_companies},
            "companies_timeline": comp_gen_timelines[idx],
        }

        processed_approaches[approach_index].update(companies_object)

    return processed_approaches


async def get_profiles_from_filters(filters, es_client):
    payload = create_search_payload(**filters)

    for i in range(3):

        profiles_ids = requests.post(
            url=os.getenv("M2M_ROUTE"),
            headers={"Authorization": os.getenv("M2M_BEARER")},
            json=payload,
        )

        if profiles_ids.status_code != 200:
            print(
                f"Issue with m2m route, status = {profiles_ids.status_code}, data = {profiles_ids.json()}"
            )
            if i == 2:
                print("Wasnt able to get profiles after 3 attempts")
                return "", 0, {}
            print("Retrying")
        else:
            break

    profiles_ids = profiles_ids.json()
    num_profiles = len(profiles_ids["profiles"])
    print(f"Num profiles = {num_profiles}")

    profiles_ids = {
        profile_id["id"]: profile_id["experienceHits"]
        for profile_id in profiles_ids["profiles"][:100]
    }

    selected_profiles = list(profiles_ids.keys())

    selected_profiles = sample_ids(selected_profiles)

    profile_data = await get_profiles_from_es(selected_profiles, es_client)

    profiles = profile_data

    formatted_profile_data = format_profile_data_complete(
        profiles=profiles, profile_experience_hits=profiles_ids
    )

    return formatted_profile_data, num_profiles, profiles

async def profile_evaluator(query, profile_data):
    system = """<role> You evaluate prospect profiles based on a checklist </role>
<instructions>
- Be methodical with your approach
- Look at the profile given to you and check it against each criteria
- For each criteria check how completely does the profile fulfill it. 
- Score the profile for each criteria between 0 and 1 (continous range, partial score is possible)
- The score for each criteria should be multiplied by the weightage for that criteria
</instructions>
<output format>
- At the end of your response output the average precision score as a number between 0 and 1 in <precision> tags
</output format>"""

    user_prompt = f"<criteria>\n{query}\n</criteria>\n\n<profile data>\n{profile_data}\n</profile data>"

    res = await asynchronous_llm(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt}
        ], model="claude-3-5-haiku-latest", provider="anthropic", temperature=0
    )

    precision_score = extract_generic("<precision>", "</precision>", res)
    precision_score = eval(precision_score)
    return precision_score, res

async def calculate_precision_for_all(query, formatted_profile_data):
    if not formatted_profile_data:
        return 0, ["No profiles came up for this approach"], []
    tasks = []
    for data in formatted_profile_data:
        tasks.append(profile_evaluator(query, data))

    precision_results = await asyncio.gather(*tasks)
    precision_scores = [i[0] for i in precision_results]
    precision_scores_avg = mean(precision_scores)
    precision_reasoning = [i[1] for i in precision_results]

    return precision_scores_avg, precision_reasoning, precision_scores

async def feedback_aggregator(profile_evaluation: str):
    system = """<role> You are an expert summarizer </role>"""

    user = f"""<task>
- You will be given some evaluation reports on multiple profiles
- You need to generate a short condensed summary (5-6 lines)
- Each profile has some characteristics that were good and some were bad.
- You need to summarize these characteristics and provide me a summary of what was good in the profiles and what shortcomings they had, with specific examples
- Do not give recommendations on your own
- I'll be using your findings to optimize my search filters so help me understand the shortcomings with actual examples from the reports
- Try to avoid repetitions and combine / coalesce similar findings 
</task>

<example>
- A lot of people were in the AI or Saas Space but no explicit scaling experience
- Instead of President, got some VPs of Marketing which is bad and doesn't align with the search criteria
<example>

<output format>
- Output the summarized findings in <findings> tags and in one paragraph
- Only focus on short comings
</output format>

<profile_reports>
{profile_evaluation}
<profile_reports>"""
    res = await asynchronous_llm(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ], temperature=0, model="claude-3-5-haiku-latest", provider="anthropic"
    )
    
    return res

async def get_feedback(eval_criteria, filters, es_client):
    cleaned_filters = clean_results(filters)
    reversed_output = await reverse_output_to_input(cleaned_filters)
    processed_approaches = await process_approaches([reversed_output])
    processed_filters = processed_approaches[0]

    formatted_profile_data, num_profiles, _ = await get_profiles_from_filters(processed_filters, es_client) 

    avg_precision_score, precision_reasoning, _ = await calculate_precision_for_all(eval_criteria, formatted_profile_data)
    
    aggregated_feedback = await feedback_aggregator("\n\n".join(precision_reasoning))

    aggregated_feedback = f"{aggregated_feedback}\nNumber of Profiles fetched: {num_profiles}"
    
    return aggregated_feedback



async def main():
    es_client = make_es_connection(async_flag=True)

    query = "President/CEO/COO from the wearable tech industry" ## ENTER QUERY HERE

    try:
        eval_criteria = await create_criteria(query)

        filters = {
            "job_title/business_function": {
                "current": [{"title_name": "CEO", "min_staff": 0, "max_staff": 50000000}],
                "past": [{"title_name": "COO", "min_staff": 0, "max_staff": 50000000}],
                "both": [{"title_name": "President", "min_staff": 0, "max_staff": 50000000}],
                "event": "CURRENT"  # Can only be "CURRENT", "PAST", "CURRENT OR PAST", "CURRENT AND PAST"
            }
        }

        feedback = await get_feedback(eval_criteria, filters, es_client)

        print(feedback)

    except:
        traceback.print_exc()
    finally:
        await es_client.close()


asyncio.run(main())