import os
from typing import Dict
from copy import deepcopy
from datetime import datetime, timezone
from app.utils.outreach.utils.days_convert import days_to_years_months
from app.utils.outreach.utils.gpt_utils.gpt_runner import gpt_runner
from app.utils.outreach.utils.summary_generation.generate_summary_prompt import (
    SUMMARY_USER_PROMPT,
    SUMMARY_SYSTEM_PROMPT,
    SUMMARY_SYSTEM_PROMPT_V2,
)

import json

from dotenv import load_dotenv

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT")
# GPT_COST_EFFICIENT_MODEL = os.getenv("GPT_COST_EFFICIENT_MODEL")


async def generate_summary(
    profileData: Dict[str, any], sample_flag=False, reference_msg=""
) -> str:
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

    profile_experience = ""
    if profileData["fullName"] == "":
        profileName = profileData["firstName"] + " " + profileData["lastName"]
    else:
        profileName = profileData["fullName"]

    # profileName = profileData["firstName"]

    aboutMe = profileData.get("summary", "N/A")
    # experience = profileData.get("experience", "")
    experience = profileData.get("experience", [])
    # print("experience", experience)

    if profileName:
        profile_experience += f"Name of Person: {profileName}\n"

    if aboutMe:
        profile_experience += f"About me of the person: {aboutMe}\n"

    if experience:
        # Separate current and past experiences based on 'end' field
        current_experiences = []
        past_experiences = []

        for exp in experience:
            if exp.get("end") is None:  # Current experience (no end date)
                current_experiences.append(exp)
            else:  # Past experience (has end date)
                past_experiences.append(exp)

        # Sort past experiences by end date (most recent first)
        past_experiences.sort(key=lambda x: x.get("end", ""), reverse=True)

        # Take up to 3 experiences total, prioritizing current ones
        selected_experiences = (
            current_experiences + past_experiences[: 3 - len(current_experiences)]
        )
        selected_experiences = selected_experiences[:3]  # Ensure we don't exceed 3

        if selected_experiences:

            # Process current experiences
            if current_experiences:
                profile_experience += "\n<current_experience>\n"
                for exp in current_experiences[:3]:  # Max 3 current
                    exp_title = exp.get("title", "N/A")
                    exp_description = exp.get("description")
                    exp_company_name = exp.get("company_name") or exp.get(
                        "companyName", "N/A"
                    )

                    profile_experience += f"Company: {exp_company_name}\n"
                    profile_experience += f"Job Title: {exp_title}\n"
                    profile_experience += f"Description: {exp_description if exp_description else 'N/A'}\n"

                    # Calculate experience duration for current job
                    start_date = exp.get("start")
                    if start_date:
                        try:
                            start_dt = datetime.fromisoformat(
                                start_date.replace("Z", "+00:00")
                            )
                            current_dt = datetime.now(timezone.utc)
                            days_worked = (current_dt - start_dt).days
                            if days_worked > 0:
                                years, typee = await days_to_years_months(days_worked)
                                profile_experience += (
                                    f"Experience at work so far: {years} {typee}\n"
                                )
                        except Exception as e:
                            print(
                                "Error in calculating experience duration for current job",
                                e,
                            )
                            pass
                    profile_experience += "\n"
                profile_experience += "</current_experience>\n"

            # Process past experiences
            remaining_past = [
                exp for exp in past_experiences if exp not in current_experiences
            ]
            remaining_slots = 3 - len(current_experiences)
            if remaining_past and remaining_slots > 0:
                profile_experience += "\n<past_experiences>\n"
                for exp in remaining_past[:remaining_slots]:
                    exp_title = exp.get("title", "N/A")
                    exp_description = exp.get("description")
                    exp_company_name = exp.get("company_name") or exp.get(
                        "companyName", "N/A"
                    )

                    profile_experience += f"Company: {exp_company_name}\n"
                    profile_experience += f"Job Title: {exp_title}\n"
                    profile_experience += f"Description: {exp_description if exp_description else 'N/A'}\n"

                    # Calculate experience duration for past job
                    start_date = exp.get("start")
                    end_date = exp.get("end")
                    if start_date and end_date:
                        try:
                            start_dt = datetime.fromisoformat(
                                start_date.replace("Z", "+00:00")
                            )
                            end_dt = datetime.fromisoformat(
                                end_date.replace("Z", "+00:00")
                            )
                            days_worked = (end_dt - start_dt).days
                            if days_worked > 0:
                                years, typee = await days_to_years_months(days_worked)
                                profile_experience += (
                                    f"Experience at work: {years} {typee}\n"
                                )
                        except:
                            pass
                    profile_experience += "\n"
                profile_experience += "</past_experiences>\n"

    system_prompt_summary = ""

    if sample_flag:
        model = "gpt-4.1"
        json_format = True
    else:
        model = "gpt-4o-mini"

    if not reference_msg:
        json_format = False
        system_prompt_summary = deepcopy(SUMMARY_SYSTEM_PROMPT)

    if not system_prompt_summary:
        json_format = True
        system_prompt_summary = deepcopy(SUMMARY_SYSTEM_PROMPT_V2)

    # if sample_flag:
    #     model = "gpt-4o"
    #     json_format = True
    #     system_prompt_summary = deepcopy(SUMMARY_SYSTEM_PROMPT_V2)
    # else:
    #     model = "gpt-4o-mini"
    #     json_format = True
    #     system_prompt_summary = deepcopy(SUMMARY_SYSTEM_PROMPT_V2)
    # system_prompt_summary = system_prompt_summary.format(
    #     profileName=profileName,
    #     aboutMe=aboutMe,
    #     currentJobTitle=currentJobTitle,
    #     currentCompany=currentCompany,
    #     profile_experience=profile_experience,
    # )
    user_prompt_summary = deepcopy(SUMMARY_USER_PROMPT)
    user_prompt_summary = user_prompt_summary.format(
        profile_data=profile_experience,
    )

    if reference_msg:
        user_prompt_summary += f"\nReference Message: {reference_msg}\n\n In case any specific receiver's experience being targetted here, only use that in summary"

    # print(user_prompt_summary)

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
            chat=chat, temperature=0.3, model=model, json_format=json_format
        )
    else:
        profile_summary = await gpt_runner(
            chat=chat, temperature=0.3, model=model, json_format=json_format
        )
    # print(time.time() - start_time)

    if json_format:
        profile_summary = json.loads(profile_summary)
        profile_summary = profile_summary["summary"]

    if isinstance(profile_summary, list):
        profile_summary = "none"
    if not isinstance(profile_summary, str):
        profile_summary = "none"

    return profile_summary
