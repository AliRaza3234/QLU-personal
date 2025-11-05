import os
from typing import Dict
from copy import deepcopy
from app.utils.dialer.utils.days_convert import days_to_years_months
from app.utils.dialer.utils.gpt_utils.gpt_models import GPT_COST_EFFICIENT_MODEL
from app.utils.dialer.utils.gpt_utils.gpt_runner import gpt_runner
from app.utils.dialer.utils.prof_summary_generation.generate_prof_summary_prompt import (
    SUMMARY_USER_PROMPT,
    SUMMARY_SYSTEM_PROMPT,
)

from dotenv import load_dotenv

load_dotenv()

# GPT_MAIN_MODEL = os.getenv("GPT_MAIN_MODEL")
# print(GPT_MAIN_MODEL)
# GPT_MAIN_MODEL = "openai/gpt-4o"
# GPT_COST_EFFICIENT_MODEL = "openai/gpt-3.5-turbo"
# GPT_BACKUP_MODEL = "openai/gpt-4"
ENVIRONMENT = os.getenv("ENVIRONMENT")
# GPT_COST_EFFICIENT_MODEL = os.getenv("GPT_COST_EFFICIENT_MODEL")


async def generate_summary(profileData: Dict[str, any]) -> str:
    """
    Asynchronously generates a summary for a profile based on provided data including personal information,
    job experience, and other relevant attributes.

    The function constructs a detailed summary by extracting and formatting data such as the profile name, about me section,
    current job title, company name, and a concise listing of past job experiences. The processed data is formatted into a prompt
    for an AI model that generates a coherent and professional summary of the profile.

    Parameters:
        profileData (Dict[str, any]): A dictionary containing details of the person's profile, such as name, summary, experience,
                                      current job title, and company name.

    Returns:
        str: A string that represents the generated summary of the person's profile.

    Raises:
        KeyError: If essential keys are missing in the profileData.
        ValueError: If the experience data is improperly structured.
    """
    if profileData["fullName"] == "":
        profileName = profileData["firstName"] + " " + profileData["lastName"]
    else:
        profileName = profileData["fullName"]
    # profileName = profileData["firstName"]

    aboutMe = profileData.get("summary", "")
    experience = profileData.get("experience", "")
    currentCompany = profileData.get("currentCompanyName", "")
    currentJobTitle = profileData.get("title", "")

    profile_experience = "\nEntire past experience:\n"
    exp_count = 0
    for exp in experience:
        if exp_count >= 3:
            break

        exp_title = exp.get("title", "")
        exp_description = exp.get("description", "")
        exp_company_name = exp.get("company_name", "")
        exp_days_worked = exp.get("exp_days", 0)
        years, typee = await days_to_years_months(exp_days_worked)

        profile_experience += f"""
        Job Title: {exp_title}
        Job Description: {exp_description}
        Company Name: {exp_company_name}
        Experience at work: {years} {typee}
        """
        exp_count += 1

    system_prompt_summary = deepcopy(SUMMARY_SYSTEM_PROMPT)
    system_prompt_summary = system_prompt_summary.format(
        profileName=profileName,
        aboutMe=aboutMe,
        currentJobTitle=currentJobTitle,
        currentCompany=currentCompany,
        profile_experience=profile_experience,
    )
    user_prompt_summary = deepcopy(SUMMARY_USER_PROMPT)
    user_prompt_summary = user_prompt_summary.format(
        profileName=profileName,
        aboutMe=aboutMe,
        currentJobTitle=currentJobTitle,
        currentCompany=currentCompany,
        profile_experience=profile_experience,
    )

    # start_time = time.time()

    chat = [
        {"role": "system", "content": system_prompt_summary},
        {"role": "user", "content": user_prompt_summary},
    ]

    # print(system_prompt_summary)
    # print("USER_PROMPT:")
    # print(user_prompt_summary)
    if ENVIRONMENT == "production":
        profile_summary = await gpt_runner(
            chat=chat, temperature=0.3, model="gpt-3.5-turbo"
        )
    else:
        profile_summary = await gpt_runner(
            chat=chat, temperature=0.3, model="gpt-4o-mini"
        )
    # print(time.time() - start_time)
    # print(profile_summary)
    return profile_summary
