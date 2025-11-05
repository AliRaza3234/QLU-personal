import asyncio

from qutils.llm.asynchronous import invoke

from app.utils.aisearch_final.prompts import *
from qutils.encode.asynchronous import embed
import re, os, unicodedata
from copy import deepcopy

from app.utils.qlu2_features.aisearch.utilities.helper_functions.postgres_functions import (
    insert_into_cache_single_entity_results,
)


async def search_similar(query, filter_type, client, top_k: int = 1):
    if filter_type == "filters":
        collection = "extract_filter_"
    elif filter_type == "companies":
        collection = "shorten_prompt_"
    else:
        return []

    collection += os.getenv("ENVIRONMENT", "staging")

    embedding = await embed([clean_string(query)])
    try:
        search_result = await asyncio.wait_for(
            client.query_points(
                collection_name=collection,
                query=embedding[0],
                limit=top_k,
                with_payload=True,
            ),
            timeout=5.0,  # seconds
        )
    except:
        return []
    results = []
    for hit in search_result.points:
        try:
            results.append(
                {"original": hit.payload["query"], "llm": hit.payload["response"]}
            )
        except Exception as e:
            print("QDRANT ISSUE: ", e)
    return results


async def ES_company_people_search(query, filter_type, connection, top_k: int = 1):
    if filter_type == "filters":
        collection = "extract_filter"
    elif filter_type == "companies":
        collection = "shorten_prompt"
    else:
        return []

    body = {"query": {"match": {"example": clean_string(query)}}, "size": top_k}
    response = await connection.search(index=collection, body=body)
    data = []
    for hit in response["hits"]["hits"]:
        try:
            data.append(
                {
                    "original": hit["_source"]["payload"]["query"],
                    # "cleaned": hit["_source"]["cleaned"],
                    "llm": hit["_source"]["payload"]["response"],
                }
            )
        except Exception as e:
            print("ES ISSUE: ", e)

    return data


def clean_string(text):
    if not text or not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    text = re.sub(r"[\xa0\u00a0]", " ", text)
    text = re.sub(r"[" "`´]", "'", text)
    text = re.sub(r'[""„"«»]', '"', text)
    text = re.sub(r"[–—]", "-", text)
    text = re.sub(r"…", "...", text)
    text = re.sub(r"[^a-z0-9\s\-\'\".,!?;:()]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"([.!?])\1+", r"\1", text)
    text = re.sub(r"(\s[\'\".,!?;:])|([\'\".,!?;:]\s)", r"\1\2", text)
    text = re.sub(r"(?<!\w)'|'(?!\w)", " ", text)
    text = text.strip()
    text = re.sub(r"^[^\w]+|[^\w]+$", "", text)
    return text


async def groq(messages, model=None, system_prompt="", retries=3):
    # if not model:
    model = "groq/openai/gpt-oss-120b"  # /claude-sonnet-4-20250514"
    for i in range(retries):
        try:
            if system_prompt:
                messages = [{"role": "system", "content": system_prompt}] + messages

            response = await invoke(
                messages=messages,
                temperature=0.1,
                model=model,
                fallbacks=["anthropic/claude-sonnet-4-20250514", "openai/gpt-4.1"],
            )
            # print("\n\n\n", "-"*50)
            # print(response)
            # print("-"*50)
            final_response = response.replace("null", "None")
            return final_response
        except Exception as e:
            print(f"Claude error: {e}")
            pass


async def claude(messages, model=None, system_prompt="", retries=3):
    if not model:
        model = "anthropic/claude-sonnet-4-20250514"
    for i in range(retries):
        try:
            if system_prompt:
                messages = [{"role": "system", "content": system_prompt}] + messages

            response = await invoke(
                messages=messages,
                temperature=0.1,
                model=model,
                fallbacks=["anthropic/claude-3-7-sonnet-latest", "openai/gpt-4.1"],
            )
            # print("\n", "-"*50)
            # print(response)
            # print("-"*50)
            final_response = response.replace("null", "None")
            return final_response
        except Exception as e:
            print(f"Claude error: {e}")
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
        print("company tenure error")
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
        if "job_title" in output_data:
            # Extract all includes and excludes from each timing category
            current_include = (
                output_data["job_title"].get("current", {}).get("include", [])
            )
            current_exclude = (
                output_data["job_title"].get("current", {}).get("exclude", [])
            )
            past_include = output_data["job_title"].get("past", {}).get("include", [])
            past_exclude = output_data["job_title"].get("past", {}).get("exclude", [])
            either_include = (
                output_data["job_title"].get("either", {}).get("include", [])
            )
            either_exclude = (
                output_data["job_title"].get("either", {}).get("exclude", [])
            )

            # Find common elements between current and past includes
            common_include_elements = set(current_include) & set(past_include)

            # Move common elements to either category
            either_include.extend(
                item for item in common_include_elements if item not in either_include
            )

            # Remove common elements from current and past
            current_include = [
                item for item in current_include if item not in common_include_elements
            ]
            past_include = [
                item for item in past_include if item not in common_include_elements
            ]

            # Initialize input_data structure
            input_data["job_title"] = {"event": None, "filter": {}}

            # Determine event type based on what categories have includes
            has_current = bool(current_include) or bool(current_exclude)
            has_past = bool(past_include) or bool(past_exclude)
            has_either = bool(either_include) or bool(either_exclude)

            if has_current and not has_past and not has_either:
                input_data["job_title"]["event"] = "CURRENT"
            elif has_past and not has_current and not has_either:
                input_data["job_title"]["event"] = "PAST"
            else:
                # Check if event field specifies AND or OR, default to OR
                event_field = output_data["job_title"].get("event", "").upper()
                input_data["job_title"]["event"] = next(
                    (item for item in ["OR", "AND"] if item in event_field), "OR"
                )

            # Build filter structure for included items
            input_data["job_title"]["filter"].update(
                {
                    title: {"type": "CURRENT", "exclusion": False}
                    for title in current_include
                }
            )
            input_data["job_title"]["filter"].update(
                {title: {"type": "PAST", "exclusion": False} for title in past_include}
            )
            input_data["job_title"]["filter"].update(
                {
                    title: {"type": "BOTH", "exclusion": False}
                    for title in either_include
                }
            )

            # Build filter structure for excluded items
            input_data["job_title"]["filter"].update(
                {
                    title: {"type": "CURRENT", "exclusion": True}
                    for title in current_exclude
                }
            )
            input_data["job_title"]["filter"].update(
                {title: {"type": "PAST", "exclusion": True} for title in past_exclude}
            )
            input_data["job_title"]["filter"].update(
                {title: {"type": "BOTH", "exclusion": True} for title in either_exclude}
            )

        if input_data.get("job_title", {}).get("filter"):
            main_output["title"] = input_data.get("job_title", {})
    except:
        print("title error")
        pass

    range_either_max = 50000000
    range_either_min = 1
    range_either_flag = False

    range_current_max = 50000000
    range_current_min = 1
    range_current_flag = False

    range_past_max = 50000000
    range_past_min = 1
    range_past_flag = False

    if output_data.get("employee_count_range"):
        if output_data.get("employee_count_range").get("either"):
            if output_data.get("employee_count_range").get("either").get("min"):
                range_either_min = (
                    output_data.get("employee_count_range").get("either").get("min")
                )
                range_either_flag = True
            if (
                output_data.get("employee_count_range").get("either").get("max")
                and output_data.get("employee_count_range").get("either").get("max")
                != 1000000
            ):
                range_either_max = (
                    output_data.get("employee_count_range").get("either").get("max")
                )
                range_either_flag = True

        if output_data.get("employee_count_range").get("current"):
            if output_data.get("employee_count_range").get("current").get("min"):
                range_current_min = (
                    output_data.get("employee_count_range").get("current").get("min")
                )
                range_current_flag = True
            if (
                output_data.get("employee_count_range").get("current").get("max")
                and output_data.get("employee_count_range").get("current").get("max")
                != 1000000
            ):
                range_current_max = (
                    output_data.get("employee_count_range").get("current").get("max")
                )
                range_current_flag = True

        if output_data.get("employee_count_range").get("past"):
            if output_data.get("employee_count_range").get("past").get("min"):
                range_past_min = (
                    output_data.get("employee_count_range").get("past").get("min")
                )
                range_past_flag = True
            if (
                output_data.get("employee_count_range").get("past").get("max")
                and output_data.get("employee_count_range").get("past").get("max")
                != 1000000
            ):
                range_past_max = (
                    output_data.get("employee_count_range").get("past").get("max")
                )
                range_past_flag = True

    if main_output.get("title"):
        for key, value in main_output.get("title").get("filter", {}).items():
            if value.get("type") == "CURRENT":
                value["min"] = range_current_min
                value["max"] = range_current_max
                range_current_flag = False

            elif value.get("type") == "PAST":
                value["min"] = range_past_min
                value["max"] = range_past_max
                range_past_flag = False

            elif value.get("type") == "BOTH":
                value["min"] = range_either_min
                value["max"] = range_either_max
                range_either_flag = False

    try:
        if "companies" in output_data:
            text = output_data["companies"]

            if range_past_flag:
                if not text.get("past", ""):
                    if output_data.get("revenue", {}).get("past"):
                        text["past"] = (
                            f"""{output_data.get("revenue", "").get("past")} Companies"""
                        )
                    else:
                        text["past"] = f"Companies with "
                        new_flag = False
                        if range_past_min > 1:
                            text["past"] += f"{range_past_min}"
                            new_flag = True
                        if range_past_max < 50000000:
                            text["past"] += (
                                f" to {range_past_max} employees"
                                if new_flag
                                else f"{range_past_max} employees at most"
                            )
                        else:
                            text["past"] += f" employees at least"

            if range_current_flag:
                if not text.get("current", ""):
                    if output_data.get("revenue", {}).get("current"):
                        text["current"] = (
                            f"""{output_data.get("revenue", "").get("current")} Companies"""
                        )
                    else:
                        text["current"] = f"Companies with "
                        new_flag = False
                        if range_current_min > 1:
                            text["current"] += f"{range_current_min}"
                            new_flag = True
                        if range_current_max < 50000000:
                            text["current"] += (
                                f" to {range_current_max} employees"
                                if new_flag
                                else f"{range_current_max} employees at most"
                            )
                        else:
                            text["current"] += f" employees at least"

            if range_either_flag:
                if (
                    not text.get("either", "")
                    and not text.get("current")
                    and not text.get("past")
                ):
                    if output_data.get("revenue", {}).get("either") and isinstance(
                        output_data.get("revenue", {}).get("either"), str
                    ):
                        text["either"] = (
                            f"""{output_data.get("revenue", "").get("either")} Companies"""
                        )
                    else:
                        text["either"] = f"Companies with "
                        new_flag = False
                        if range_either_min > 1:
                            text["either"] += f"{range_either_min}"
                            new_flag = True
                        if range_either_max < 50000000:
                            text["either"] += (
                                f" to {range_either_max} employees"
                                if new_flag
                                else f"{range_either_max} employees at most"
                            )
                        else:
                            text["either"] += f" employees at least"

            if text.get("current"):
                text["current"] = [text.get("current").capitalize()]
            if text.get("past"):
                text["past"] = [text.get("past").capitalize()]
            if text.get("either"):
                text["either"] = [text.get("either").capitalize()]

            if text.get("current") and not text.get("past"):
                if not text.get("either"):
                    output_data["companies"] = {
                        "current": text.get("current"),
                        "past": None,
                        "timeline": "CURRENT",
                    }
                else:
                    output_data["companies"] = {
                        "current": text.get("current"),
                        "past": text.get("either"),
                        "timeline": "AND",
                    }
            # Case 3: Only past prompt generated
            elif text.get("past") and not text.get("current"):
                if not text.get("either"):
                    output_data["companies"] = {
                        "past": text.get("past"),
                        "current": None,
                        "timeline": "PAST",
                    }
                else:
                    output_data["companies"] = {
                        "past": text.get("past"),
                        "current": text.get("either"),
                        "timeline": "AND",
                    }
            # Case 4: Both current and past prompts generated
            elif text.get("past") and text.get("current"):
                output_data["companies"] = {
                    "past": text.get("past"),
                    "current": text.get("current"),
                    "timeline": "AND",
                }
            # Case 5: Only either prompt generated
            elif text.get("either"):
                output_data["companies"] = {
                    "past": None,
                    "current": text.get("either"),
                    "timeline": "OR",
                }

            if (
                not text.get("either")
                and not text.get("past")
                and not text.get("current")
            ):
                del output_data["companies"]

        main_output["companies"] = output_data.get("companies", {})
    except Exception as e:
        raise e
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
            # print("Output_Data\n", output_data, "-"*50)
            # Find common elements between current and past (both include and exclude lists)
            current_include = set(
                output_data["location"].get("current", {}).get("include", [])
            )
            current_exclude = set(
                output_data["location"].get("current", {}).get("exclude", [])
            )
            past_include = set(
                output_data["location"].get("past", {}).get("include", [])
            )
            past_exclude = set(
                output_data["location"].get("past", {}).get("exclude", [])
            )

            # Find common elements in include lists
            common_include = current_include & past_include
            # Find common elements in exclude lists
            common_exclude = current_exclude & past_exclude

            # Get either list
            either_include = set(
                output_data["location"].get("either", {}).get("include", [])
            )
            either_exclude = set(
                output_data["location"].get("either", {}).get("exclude", [])
            )

            # Add common elements to either list if not already present
            either_include.update(
                item for item in common_include if item not in either_include
            )
            either_exclude.update(
                item for item in common_exclude if item not in either_exclude
            )

            # Create both list from either
            output_data["location"]["both"] = {
                "include": list(either_include),
                "exclude": list(either_exclude),
            }

            # Remove common elements from current and past
            output_data["location"]["current"] = {
                "include": [
                    item
                    for item in output_data["location"]
                    .get("current", {})
                    .get("include", [])
                    if item not in common_include
                ],
                "exclude": [
                    item
                    for item in output_data["location"]
                    .get("current", {})
                    .get("exclude", [])
                    if item not in common_exclude
                ],
            }
            output_data["location"]["past"] = {
                "include": [
                    item
                    for item in output_data["location"]
                    .get("past", {})
                    .get("include", [])
                    if item not in common_include
                ],
                "exclude": [
                    item
                    for item in output_data["location"]
                    .get("past", {})
                    .get("exclude", [])
                    if item not in common_exclude
                ],
            }

            # Handle continent expansions for all timelines
            for timeline in ["current", "both", "past"]:
                if timeline in output_data["location"]:
                    for list_type in ["include", "exclude"]:
                        location_list = output_data["location"][timeline].get(
                            list_type, []
                        )

                        if "South America" in location_list:
                            location_list.extend(
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
                        if "North America" in location_list:
                            location_list.extend(
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
                        if "Oceania" in location_list:
                            location_list.extend(
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

            # Get all location lists
            current_include = (
                output_data["location"].get("current", {}).get("include", [])
            )
            current_exclude = (
                output_data["location"].get("current", {}).get("exclude", [])
            )
            past_include = output_data["location"].get("past", {}).get("include", [])
            past_exclude = output_data["location"].get("past", {}).get("exclude", [])
            both_include = output_data["location"].get("both", {}).get("include", [])
            both_exclude = output_data["location"].get("both", {}).get("exclude", [])

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
                        if item in output_data["location"].get("event", "").upper()
                    ),
                    "OR",
                )

            # Build filter with exclusion information
            # For current locations
            for location in current_include:
                input_data["location"]["filter"][location] = {
                    "type": "CURRENT",
                    "exclusion": False,
                }
            for location in current_exclude:
                input_data["location"]["filter"][location] = {
                    "type": "CURRENT",
                    "exclusion": True,
                }

            # For past locations
            for location in past_include:
                input_data["location"]["filter"][location] = {
                    "type": "PAST",
                    "exclusion": False,
                }
            for location in past_exclude:
                input_data["location"]["filter"][location] = {
                    "type": "PAST",
                    "exclusion": True,
                }

            # For both locations - exclusion is False if exclusion differs between current and past
            for location in both_include:
                input_data["location"]["filter"][location] = {
                    "type": "BOTH",
                    "exclusion": False,
                }
            for location in both_exclude:
                input_data["location"]["filter"][location] = {
                    "type": "BOTH",
                    "exclusion": True,
                }

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

        if input_data.get("ownership", None):
            if main_output.get("companies", None):
                companies_data = main_output["companies"]
                if companies_data.get("past", None) and not companies_data.get(
                    "current"
                ):
                    companies_data["current"] = [
                        f"""{' or '.join(input_data.get("ownership", []))} companies"""
                    ]
                    companies_data["timeline"] = "AND"
                    input_data["ownership"] = []
                elif companies_data.get("past", None):
                    input_data["ownership"] = []

        main_output["ownership"] = input_data.get("ownership", [])
    except:
        print("ownership error")
        pass

    main_output = {key: value for key, value in main_output.items() if value}
    return main_output


def clean_results(data):

    key_mapping = {
        "total_working_years": "experience",
        "job_title": "job_title",
        "management_levels": "management_level",
        "skills": "skill",
        "locations": "location",
        "names": "name",
        "isExperienceSelected": "isExperienceSelected",  # Key added as requested
    }

    for key in ["job_title", "location"]:
        if key in data:
            # Check if all nested include/exclude lists are empty
            all_empty = True
            for event_type in ["current", "past", "either"]:
                if event_type in data[key]:
                    if isinstance(data[key][event_type], dict):
                        # Check if both include and exclude lists are empty
                        include_list = data[key][event_type].get("include", [])
                        exclude_list = data[key][event_type].get("exclude", [])
                        if include_list or exclude_list:
                            all_empty = False
                            break

            # Remove the key if all nested lists are empty
            if all_empty:
                del data[key]

    # Handle management_level with the old simple list structure
    for key in ["management_level", "industry"]:
        if key in data and all(
            not data[key][k] for k in ["current", "past", "either"] if k in data[key]
        ):
            del data[key]

    # if data.get("management_level") and data.get("job_title"):
    #     if data.get("management_level", {}).get("current", []):

    #         if data.get("job_title", {}).get("current", []):

    #             data["job_title"]["current"].extend(
    #                 data.get("management_level", {}).get("current", [])
    #             )
    #             del data["management_level"]["current"]

    #     if data.get("management_level", {}).get("past", []):

    #         if data.get("job_title").get("past", []):
    #             data["job_title"]["past"].extend(
    #                 data.get("management_level", {}).get("past", [])
    #             )
    #             del data["management_level"]["past"]

    #     if data.get("management_level", {}).get("either", []):

    #         if data.get("job_title").get("either", []):

    #             data["job_title"]["either"].extend(
    #                 data.get("management_level", {}).get("either", [])
    #             )
    #             del data["management_level"]["either"]

    #     if not any(
    #         data.get("management_level", {}).get(item)
    #         for item in ["current", "past", "either"]
    #     ):
    #         del data["management_level"]

    if "companies" in data:
        if all(
            not data.get("companies", {}).get(k, None)
            for k in ["current", "either", "past"]
        ):
            del data["companies"]

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
        and data.get("role_tenure")
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
        and data.get("company_tenure")
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


async def test_main(
    query,
    es_client,
    qdrant_client,
    demoBlocked=False,
    add_to_clear_prompt="",
    testing=False,
    convId=None,
    promptId=None,
):

    # print("Starting AI Search")
    if not testing:  # and os.getenv("ENVIRONMENT", "") == "staging":
        # print("Starting AI Search With Groq")
        results = await test_main_groq(
            query,
            es_client,
            qdrant_client,
            demoBlocked,
            add_to_clear_prompt,
            convId,
            promptId,
        )
        return results

    EXTRACT_USER_PROMPT = (
        EXTRACT_USER_PROMPT_1
        + (EXTRACT_USER_PROMPT_DEMO if not demoBlocked else "")
        + EXTRACT_USER_PROMPT_TRUST_ME
    )
    retries = 1
    for index in range(retries):
        # try:
        if not has_meaningful_letters(query):
            return {}

        if index == 1:
            user_prompt = (
                user_prompt
                + " Be very mindful of the output formats above, for each filter and for the whole output."
            )
        user_prompt = f"""Here is the user query:\n\n\'''{query}'''\n\nFor each filter, first give your reasoning and then your output (ALWAYS a json object enclosed within <Output></Output> tags).\nThink logically about what the user requires, without decreasing the recall or precision, and apply filters and their current, past, and, or according to what would bring the best results to the user."""
        messages = [
            # {
            #     "role": "user",
            #     "content": [{"type": "text", "text": EXTRACT_USER_PROMPT}],
            # },
            # {"role": "assistant", "content": [{"type": "text", "text": "YES."}]},
            {"role": "user", "content": user_prompt},
        ]

        messages_companies = [
            {
                "role": "user",
                "content": f"""\n<User_Prompt>\n{query+add_to_clear_prompt}\n</User_Prompt>\nAll of the following keys — companies, revenue, and employee_count_range — must each contain both current and past subkeys, or only either. For each key, companies, revenue and employee_count_range decide which format of output suits it best. First provide reasoning and then output""",
            },
        ]
        response, response_companies = await asyncio.gather(
            *[
                claude(
                    messages,
                    system_prompt=EXTRACT_USER_PROMPT,
                ),
                claude(
                    messages_companies,
                    system_prompt=DAMN_SHORTEN_PROMPT_CLAUDE_NEW,
                ),
            ]
        )

        response = (
            response[response.rfind("<Output>") : response.rfind("</Output>")]
            .replace("<Output>", "")
            .replace("<", "")
        )
        response_companies = (
            response_companies[
                response_companies.rfind("<Output>") : response_companies.rfind(
                    "</Output>"
                )
            ]
            .replace("<Output>", "")
            .replace("<", "")
        )
        response_companies = eval(response_companies.strip())

        results = eval(response.strip())
        results["current_companys_ownership"] = response_companies.get(
            "current_companys_ownership"
        )
        if "job_title" not in results:
            results["job_title"] = {}

        # results["job_title"]["current"] = results.get("job_title", {}).get(
        #     "current", []
        # ) + results.get("business_function", {}).get("current", [])

        # results["job_title"]["past"] = results.get("job_title", {}).get(
        #     "past", []
        # ) + results.get("business_function", {}).get("past", [])

        # results["job_title"]["either"] = results.get("job_title", {}).get(
        #     "either", []
        # ) + results.get("business_function", {}).get("either", [])

        # if not results.get("job_title", {}).get("event", None):
        #     results["job_title"]["event"] = results.get("business_function", {}).get(
        #         "event", []
        #     )
        results = clean_results(results)

        results.update(response_companies)
        all_results_appended = await reverse_output_to_input(
            results, es_client, demoBlocked
        )

        return all_results_appended
    # except Exception as e:
    #     print(e)
    #     pass

    return {}


async def test_main_groq(
    query,
    es_client,
    qdrant_client,
    demoBlocked=False,
    add_to_clear_prompt="",
    convId=None,
    promptId=None,
):

    EXTRACT_USER_PROMPT = (
        EXTRACT_USER_PROMPT_1
        + (EXTRACT_USER_PROMPT_DEMO if not demoBlocked else "")
        + EXTRACT_USER_PROMPT_TRUST_ME_STAGING
    )

    retries = 3
    for index in range(retries):
        try:
            if not has_meaningful_letters(query):
                return {}

            user_prompt = f"""Here is the user query:\n\n\'''{query}'''\n\nFor each filter, first give your reasoning and then your output (ALWAYS a json object enclosed within <Output></Output> tags).\nThink logically about what the user requires, without decreasing the recall or precision, and apply filters and their current, past, and, or according to what would bring the best results to the user."""
            if index > 0:
                user_prompt = (
                    user_prompt
                    + "\n**Pay close attention to the specified output formats**, both for each individual filter and for the overall output."
                )

            messages = [
                # {
                #     "role": "user",
                #     "content": [{"type": "text", "text": EXTRACT_USER_PROMPT}],
                # },
                # {"role": "assistant", "content": [{"type": "text", "text": "YES."}]},
                {"role": "user", "content": user_prompt},
            ]

            messages_companies = [
                {
                    "role": "user",
                    "content": f"""\n<User_Prompt>\n{query+add_to_clear_prompt}\n</User_Prompt>\nAll of the following keys — companies, revenue, and employee_count_range — must each contain both current and past subkeys, or only either. For each key, companies, revenue and employee_count_range decide which format of output suits it best. First provide reasoning and then output. **Always generate the whole reasoning similar to how reasoning was generated in the examples provided to you**""",
                },
            ]

            (
                top_results_filters,
                top_results_companies,
                embeddings_results_filters,
                embeddings_results_companies,
            ) = await asyncio.gather(
                *[
                    ES_company_people_search(query, "filters", es_client),
                    ES_company_people_search(query, "companies", es_client),
                    search_similar(query, "filters", qdrant_client),
                    search_similar(query, "companies", qdrant_client),
                ]
            )
            # print("-" * 20, "PRINT STATEMENTS", "-" * 20)
            # print(
            #     len(top_results_filters),
            #     len(top_results_companies),
            #     len(embeddings_results_filters),
            #     len(embeddings_results_companies),
            # )
            # print("-" * 20, "END OF PRINT STATEMENTS", "-" * 20)

            fetched_examples_for_logging = {
                "es_filters_examples": deepcopy(top_results_filters),
                "es_companies_examples": deepcopy(top_results_companies),
                "embeddings_filters_examples": deepcopy(embeddings_results_filters),
                "embeddings_companies_examples": deepcopy(embeddings_results_companies),
            }

            top_results_filters += embeddings_results_filters
            top_results_companies += embeddings_results_companies

            examples = ""
            for index, result in enumerate(top_results_filters):
                examples += f"""
    <EXAMPLE {index+1}>
        Query: {result["original"]}
        <Reasoning and Output>\n{result["llm"]}\n</Reasoning and Output>
    </EXAMPLE {index+1}>
                """

            # print("-"*50)
            # print(examples)
            # print("-"*50)

            examples_companies = ""
            for index, result in enumerate(top_results_companies):
                examples_companies += f"""
    <EXAMPLE {index+1}>
        Query: {result["original"]}
        <Reasoning and Output>\n{result["llm"]}\n</Reasoning and Output>
    </EXAMPLE {index+1}>
                """

            system_prompt_filters = (
                EXTRACT_USER_PROMPT
                + f"""
The following are some examples of how you should reason based on the user query:
    <EXAMPLES FOR REFERENCE>
    {examples}
    </EXAMPLES FOR REFERENCE>

You must also generate your own <Reasoning and Output> tags for the user query you receive and reason accordingly.
            """
                if examples
                else EXTRACT_USER_PROMPT
            )
            system_prompt_companies = (
                DAMN_SHORTEN_PROMPT_CLAUDE_NEW
                + f"""
The following are some examples of how you should reason based on the user query:
    <EXAMPLES FOR REFERENCE>
    {examples_companies}
    </EXAMPLES FOR REFERENCE>

You must also generate your own <Reasoning and Output> tags for the user query you receive and reason accordingly.
            """
                if examples_companies
                else DAMN_SHORTEN_PROMPT_CLAUDE_NEW
            )

            response, response_companies = await asyncio.gather(
                *[
                    groq(
                        messages,
                        system_prompt=system_prompt_filters,
                    ),
                    groq(
                        messages_companies,
                        system_prompt=system_prompt_companies,
                        # model = "anthropic/claude-sonnet-4-20250514"
                    ),
                ]
            )

            responses_for_logging = {
                "filter_response": response,
                "companies_response": response_companies,
            }
            if convId and promptId:
                asyncio.create_task(
                    insert_into_cache_single_entity_results(
                        conversation_id=convId,
                        prompt_id=promptId,
                        response_id=-786,
                        prompt=query,
                        result={
                            "fetched_examples": fetched_examples_for_logging,
                            "responses": responses_for_logging,
                        },
                        temp=True,
                    )
                )
            # print("Here2")
            response = (
                response[response.rfind("<Output>") : response.rfind("</Output>")]
                .replace("<Output>", "")
                .replace("<", "")
            )
            response_companies = (
                response_companies[
                    response_companies.rfind("<Output>") : response_companies.rfind(
                        "</Output>"
                    )
                ]
                .replace("<Output>", "")
                .replace("<", "")
            )
            response_companies = eval(response_companies.strip())

            results = eval(response.strip())
            results["current_companys_ownership"] = response_companies.get(
                "current_companys_ownership"
            )
            if "job_title" not in results:
                results["job_title"] = {}

            results = clean_results(results)

            results.update(response_companies)
            all_results_appended = await reverse_output_to_input(
                results, es_client, demoBlocked
            )

            return all_results_appended
        except Exception as e:
            print(e)
            pass

    return {}
