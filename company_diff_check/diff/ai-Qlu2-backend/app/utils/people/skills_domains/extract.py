import json
from app.core.database import cache_data, get_cached_data
from qutils.database.post_gres import postgres_fetch_profile_data

from datetime import datetime, timezone
from qutils.llm.asynchronous import invoke


months = {
    "jan": "01-",
    "feb": "02-",
    "mar": "03-",
    "apr": "04-",
    "may": "05-",
    "jun": "06-",
    "jul": "07-",
    "aug": "08-",
    "sep": "09-",
    "oct": "10-",
    "nov": "11-",
    "dec": "12-",
}


def safe_json_parse(output):
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        try:
            start = output.find("{")
            end = output.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(output[start : end + 1])
            else:
                return {}
        except json.JSONDecodeError:
            return {}


async def extract_skills_last(payload):
    formatting = """
    {
        "Skill 1": {
            "score": 9.0,
            "last used" : "0.5 years ago"
        },
        "Skill 2": {
            "score": 8.0,
            "last used" : "1 year ago"
        },
        "Skill 3": {
            "score": 10.0,
            "last used" : "Currently in use"
        },
        "Skill 4": {
            "score": 7.5,
            "last used" : "1.5 years ago"
        },
        "Skill 5": {
            "score": 4.0,
            "last used" : "5.0 years ago"
        },
        "Skill 6": {
            "score": 3.5,
            "last used" : "5.5 years ago"       }
    }
    """

    system_prompt = f"""
    You are an intelligent AI assistant tasked with evaluating a person's skills based on their experiences, which are listed chronologically with the number of days spent in each. Your job is to assign a score from 1 to 10 for each skill of the person, based ONLY on the time since that skill was used. 
    """

    todays_date = datetime.now(timezone.utc).strftime("%m-%Y")
    user_prompt = f"""
    When evaluating, ONLY prioritize the most recently used skills and ensure that scores are a reflection of this priority. In 'last used', explicitly write the calculated duration, in years, of when the skill was LAST USED.
    Take a deep breath and read carefully. If a skill was used EARLIER in time, it should mean LOWER scores. For example, 4 years ago will have a LESSER score than 2 years ago. Same durations will have same values.
    Some skills can be similar in multiple experiences, in which case you will take the last experience duration into account ONLY. 0 years ago should be written as mean CURRENTLY IN USE.
    Very Important Instruction:
    Always return a json object. Always STRICTLY follow this output format:
    
    {formatting}

    IMPORTANT: 'Skill 1', Skill 2', ... will NEVER BE INCLUDED in the output. THEY ARE TO BE REPLACED BY RELEVANT AND LOGICAL SKILLS.

    Same durations will have same values.
    The attribute 'skillsLast' will either be empty list or a list of skills. 
    - If its a list of skills, then ENSURE that each skill is from the skillsLast attribute ONLY.
    - If its an empty list then you should extract relevant skills based on the any of the data provided.

    We will be checking our database using only these skills so ensure that NO OTHER skill is extracted. If skill
    Also explain how you calculated the last used key.
    
    """

    messages = [{"role": "system", "content": system_prompt}]
    messages.append(
        {"role": "user", "content": user_prompt + f"Here's the data:\n\n{payload}"}
    )
    output = await invoke(
        messages=messages,
        temperature=0,
        model="openai/gpt-4o-mini",
        fallbacks=["anthropic/claude-3-5-haiku-latest"],
    )

    data = safe_json_parse(output)
    return data


async def extract_skills_experience(payload):
    formatting = """
    {
        "Skill 1": {
            "score": 9.0,
            "duration" : "10 years"
        },
        "Skill 2": {
            "score": 8.0,
            "duration" : "10 years"
        },
        "Skill 3": {
            "score": 10.0,
            "duration" : "15 years"
        },
        "Skill 4": {
            "score": 7.5,
            "duration" : "9 years"
        },
        "Skill 5": {
            "score": 4.0,
            "duration" : "2 years"
        },
        "Skill 6": {
            "score": 3.5,
            "duration" : "1.5 years"       }
    }
    """

    system_prompt = f"""
    You are an intelligent AI assistant tasked with evaluating a person's skills based on their experiences, which are listed chronologically with the number of days spent in each. Your job is to assign a score from 1 to 10 for each skill, based ON the duration of relevant experiences.
    """

    user_prompt = f"""
    When evaluating, prioritize skills related to the most long durations of experiences and ensure that scores reflect this priority. Avoid redundancy by ensuring that each skill is represented under one main category. In 'duration', explicitly write the given duration, in years, of each skill. Same durations should have the same score.
    NEVER change the given duration
    Longer duration should mean higher scores. The durations or scores can never be 0.
    Some skills can be similar in multiple experiences, in which case you will take both experiences duration into account.
    Very Important Instruction:
    Always strictly follow this output format. (Output should always be a json object)
    
    {formatting}

    IMPORTANT: 'Skill 1', Skill 2', ... will NEVER BE INCLUDED in the output. THEY ARE TO BE REPLACED BY RELEVANT AND LOGICAL SKILLS.

    Also explain how you calculated the durations.
    
    """

    messages = [{"role": "system", "content": system_prompt}]
    messages.append(
        {"role": "user", "content": user_prompt + f"Here's the data:\n\n{payload}"}
    )

    output = await invoke(
        messages=messages,
        temperature=0,
        model="openai/gpt-4o-mini",
        fallbacks=["anthropic/claude-3-5-haiku-latest"],
    )

    data = safe_json_parse(output)
    return data


def months_between(start_date, end_date):
    # Calculate the difference in months between two dates
    months = (end_date.year - start_date.year) * 12 + (
        end_date.month - start_date.month
    )

    # Adjust for partial months
    if end_date.day < start_date.day:
        months -= 1

    return months


async def extract_skills_domains_new(payload, db_client):
    type_payload = payload.type
    esId = payload.esId

    if type_payload.lower().strip() == "skills":
        skills_result = await get_cached_data(
            f"{esId}_skills", "cache_extract_skills_domains_new"
        )
        if skills_result:
            return skills_result
    elif type_payload.lower().strip() == "domains":
        domains_result = await get_cached_data(
            f"{esId}_domains", "cache_extract_skills_domains_new"
        )
        if domains_result:
            return domains_result
    else:
        return {}

    result = await postgres_fetch_profile_data(
        db_client, [esId], ["experience", "companies"]
    )

    result = result[esId]

    if not result or not result.get("profile"):
        return {}

    profile = result["profile"]

    index = 1
    days_spent = []
    experienceDescriptionList = ""
    for experience in result["experience"]:
        experienceDescriptionList += (
            f"Experience {index} title: {experience['title']}. "
        )
        experienceDescriptionList += f"Experience {index} description: "
        experienceDescriptionList += str(experience["description"])
        experienceDescriptionList += "\n"
        number_of_days = experience["tenure"]
        if not number_of_days or number_of_days == 0:
            continue

        if experience["start"] and not experience["end"]:
            endedon = datetime.now(timezone.utc)
        elif experience["start"] and experience["end"]:
            endedon = datetime.fromisoformat(experience["end"])
        else:
            continue

        time_since = months_between(endedon, datetime.now(timezone.utc))
        # startedon = datetime.fromisoformat(experience["start"])
        if time_since:
            experienceDescriptionList += f"Number of years/duration spent in this experience: {round(number_of_days/365)} years. This experience was last used {round(time_since/12)} years ago"
        else:
            experienceDescriptionList += f"Number of years/duration spent in this experience: {round(number_of_days/365)} years. This experience is currently in use."
        experienceDescriptionList += "\n\n"
        days_spent.append({f"Experience {index}": number_of_days})
        index += 1

    try:
        summary = profile["summary"]
    except:
        summary = ""

    if type_payload == "skills":
        # if profile["skills"] == None:
        #     return {}

        payload = {
            "skillsLast": profile["skills"],
            "summary": summary,
            "experienceDescriptionList": experienceDescriptionList,
        }
        attempts = 0
        while attempts < 5:
            try:
                skills_last = await extract_skills_last(payload)
                payload[
                    "experienceDescriptionList"
                ] += f'Domains include {", ".join(list(skills_last.keys()))}.'
                skills = await extract_skills_experience(payload)

                if not skills or not skills_last:
                    raise Exception("Empty skills data returned")
                break
            except:
                attempts += 1

        all = {}
        for domain in skills:
            if domain in skills_last:
                score = (skills[domain]["score"] + (skills_last[domain]["score"])) / 2
                all[domain] = {
                    "experience": skills[domain]["duration"].replace("year", "Year"),
                    "recency": skills_last[domain]["last used"].replace("year", "Year"),
                    "score": round(score, 2),
                }

        grouped_skills = {}
        for skill, data in all.items():
            key = (data["experience"], data["recency"])
            if key not in grouped_skills:
                grouped_skills[key] = []
            grouped_skills[key].append(skill)

        max_scores = {}
        for key, skills in grouped_skills.items():
            max_score = max(all[skill]["score"] for skill in skills)
            max_scores[key] = max_score

        for key, skills in grouped_skills.items():
            for skill in skills:
                all[skill]["score"] = max_scores[key]

        await cache_data(f"{esId}_skills", all, "cache_extract_skills_domains_new")

        return all
    else:
        index = 1
        total = 0
        some = {}
        end = {}
        start = None
        experience = result["experience"]
        for ind, company in enumerate(result["companies"]):
            domains = []
            try:
                domains += company["industry"]
            except:
                pass

            try:
                domains += company["specialties"]
            except:
                pass

            experienceDescriptionList += f"Domains for Experience {index}: {domains}\n"
            index += 1

            number_of_days = experience[ind]["tenure"]
            if not number_of_days:
                continue
            total = total + number_of_days
            if experience[ind]["start"] and not experience[ind]["end"]:
                endedon = datetime.now(timezone.utc)
            elif experience[ind]["start"] and experience[ind]["end"]:
                endedon = datetime.fromisoformat(experience[ind]["end"])
            else:
                continue
            startedon = datetime.fromisoformat(experience[ind]["start"])

            start_temp = startedon

            if start:
                if start_temp < start:
                    start = start_temp
            else:
                start = start_temp

            for j in set(domains):

                if j not in some:
                    some[j] = {"start": startedon, "end": endedon}
                else:
                    if some[j]["start"] > startedon:
                        some[j]["start"] = startedon

                    if some[j]["end"] < endedon:
                        some[j]["end"] = endedon

                if not endedon:
                    now_time = datetime.now(timezone.utc)
                    end_temp = datetime.now(timezone.utc)
                else:
                    end_temp = endedon

                if j not in end:
                    end[j] = end_temp
                else:
                    if end_temp > end[j]:
                        end[j] = end_temp

        if not start:
            return {}
        try:
            total = (datetime.now(timezone.utc) - start).days
        except:
            pass
        diff = (datetime.now(timezone.utc) - start).days
        duration = {}
        for key in some:
            duration[key] = (
                str(round((some[key]["end"] - some[key]["start"]).days / 365, 1))
                + " years"
            )
            some[key] = ((some[key]["end"] - some[key]["start"]).days / total) * 10

        recency = {}
        for key in end:
            temp_diff = (end[key] - start).days
            now = datetime.now(timezone.utc)  # Get current time in UTC
            time_diff = (now - end[key]).days  # Calculate difference in days

            # Check if the difference is zero and format the string accordingly
            if time_diff == 0:
                recency[key] = "Currently in use"
            else:
                recency[key] = str(round(time_diff / 365, 1)) + " years ago"
            if recency[key].lower() in [
                "0 year ago",
                "0.0 year ago",
                "0 years ago",
                "0.0 years ago",
            ]:
                recency[key] = "Currently in use"
            end[key] = (temp_diff / diff) * 10

        domains_last = {}

        for key in some:
            if key in end:
                domains_last[key] = round((some[key] + end[key]) / 2, 2)

        all = {}
        for row in domains_last:
            all[row] = {
                "experience": duration[row].replace("year", "Year"),
                "recency": recency[row].replace("year", "Year"),
                "score": domains_last[row] if domains_last[row] <= 10 else 10.0,
            }

        await cache_data(f"{esId}_domains", all, "cache_extract_skills_domains_new")
        return all


async def extract_skills(payload):
    formatting = """
    {
        "Financial Analysis": {
            "score": 9.0
        },
        "P&L Management": {
            "score": 8.0
        },
        "Financial Reporting": {
            "score": 10.0
        },
        "Budgets": {
            "score": 7.5
        },
        "Internal Controls": {
            "score": 4.0
        },
        "Accounting": {
            "score": 3.5
        }
    }
    """

    prompt = f"""
    You are an intelligent AI assistant tasked with evaluating a person's skills based on their experiences, which are listed chronologically with the number of days spent in each. """

    user_query = f"""Your job is to assign a score from 1 to 10 for each skill, influenced by the recency and duration of relevant experiences. When evaluating, prioritize skills related to the most recent experiences and ensure that scores reflect this priority. Additionally, consolidate skills into a single parent skill when multiple sub-skills pertain to it. For example, treat "EDA", "Data Cleaning", "Data-Preprocessing" as subcategories under the broader "Exploratory Data Analysis" skill, and provide a unified score for this consolidated skill. Avoid redundancy by ensuring that each skill is represented under one main category. Ensure logical skill names.

    Very Important Instruction:
    Always strictly follow this output format:
    {formatting}


    """
    messages = [{"role": "system", "content": prompt}]
    messages.append(
        {"role": "user", "content": f"{user_query}Here's the data:\n\n{payload}"}
    )

    output = await invoke(
        messages=messages,
        temperature=0,
        model="openai/gpt-4o-mini",
        fallbacks=["anthropic/claude-3-5-haiku-latest"],
    )

    data = safe_json_parse(output)
    return data


async def extract_domains(payload):
    formatting = """
    {
        "Financial Analysis": {
            "score": 9.0
        },
        "P&L Management": {
            "score": 8.0
        },
        "Financial Reporting": {
            "score": 10.0
        },
        "Budgets": {
            "score": 7.5
        },
        "Internal Controls": {
            "score": 4.0
        },
        "Accounting": {
            "score": 3.5
        }
    }
    """

    prompt = f"""
    You are an intelligent AI assistant whose job is to look at a list of domains of a person and his/her experiences with the number of days spent in a particular experience
    These experiences are sorted chronologically. Looking at the domains with experiences and the duration of experiences give me a score for each domain on a scale of 1-10.
    """

    user_prompt = f"""Make sure you look at the repetition in domains and the recency and duration within a domain to give a score. The score should be indicative of how well a domain describes the person. Ensure logical domain names.
    
    Very Important Instruction:
    Always strictly follow this output format:
    {formatting}
    
    """
    messages = []
    messages.append({"role": "system", "content": prompt})
    messages.append(
        {"role": "user", "content": f"{user_prompt}Here's the data:\n\n{payload}"}
    )

    output = await invoke(
        messages=messages,
        temperature=0,
        model="openai/gpt-4o-mini",
        fallbacks=["anthropic/claude-3-5-haiku-latest"],
    )

    data = safe_json_parse(output)
    return data


async def extract_skills_domains(payload, db_client):
    type = payload.type
    esId = payload.esId

    if type.lower().strip() == "skills":
        skills_result = await get_cached_data(
            f"{esId}_skills", "cache_extract_skills_domains"
        )
        if skills_result:
            return skills_result
    elif type.lower().strip() == "domains":
        domains_result = await get_cached_data(
            f"{esId}_domains", "cache_extract_skills_domains"
        )
        if domains_result:
            return domains_result
    else:
        return {}

    result = await postgres_fetch_profile_data(
        db_client, [esId], ["experience", "companies"]
    )

    result = result[esId]

    if not result or not result.get("profile"):
        return {}

    profile = result["profile"]

    index = 1
    days_spent = []
    experienceDescriptionList = ""
    for experience in result["experience"]:
        experienceDescriptionList += f"Experience {index} description: "
        experienceDescriptionList += str(experience["description"])
        experienceDescriptionList += "\n"
        number_of_days = experience["tenure"]
        experienceDescriptionList += (
            f"Number of days spent in this experience: {number_of_days}"
        )
        experienceDescriptionList += "\n\n"
        days_spent.append({f"Experience {index}": number_of_days})
        index += 1

    try:
        summary = profile["summary"]
    except:
        summary = ""

    if type == "skills":
        payload = {
            "entityList": profile["skills"],
            "summary": summary,
            "experienceDescriptionList": experienceDescriptionList,
        }

        attempts = 0
        skills = {}
        while attempts < 3:
            try:
                skills = await extract_skills(payload)
                if skills:
                    break
            except:
                attempts += 1
        await cache_data(f"{esId}_skills", skills, "cache_extract_skills_domains")
        return skills
    else:
        index = 1
        for company in result["companies"]:
            domains = []
            try:
                domains += company["industry"]
            except:
                pass

            try:
                domains += company["specialties"]
            except:
                pass

            experienceDescriptionList += f"Domains for Experience {index}: {domains}\n"
            index += 1

        attempts = 0
        domains = {}
        while attempts < 3:
            try:
                domains = await extract_domains(experienceDescriptionList)
                if domains:
                    break
            except:
                attempts += 1

        await cache_data(f"{esId}_domains", domains, "cache_extract_skills_domains")
        return domains
