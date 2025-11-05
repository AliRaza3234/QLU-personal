import os
from app.utils.fastmode.prompts import SUMMARY_PROMPT
from app.utils.fastmode.llms import claude


async def summary_text(person_key, entity, sub_section, main_query, es_client):
    if entity == "person":

        query = {"query": {"terms": {"public_identifier": [person_key]}}}
        results = await es_client.search(
            body=query, index=os.getenv("ES_PROFILES_INDEX", "people"), timeout="60s"
        )
        if results["hits"]["total"]["value"] == 0:
            return ""
        results = results["hits"]["hits"][0]["_source"]

        if sub_section in ["skills"] and not results.get("skills"):
            return ""

        explanation = f"""{results.get("full_name")}
    Headline: {results.get("headline")}
    Summary of Person: {results.get("summary")}
    """
        extracted_info = []
        for exp in results.get("experience", []) or {}:
            title = exp.get("title", "N/A")
            company = exp.get("company", "N/A")
            start = exp.get("start", "N/A").split("T")[0] if exp.get("start") else "N/A"
            end = exp.get("end", "Present") if exp.get("end") else "Present"
            job_summary = exp.get("job_summary", "N/A")
            company_description = exp.get("company_description", "")

            if end != "Present":
                end = end.split("T")[0]

            temp_string = f"{title} at {company} ({start} - {end}): {job_summary}."
            temp_string = (
                temp_string + f" {company} Description: {company_description}"
                if company_description
                else temp_string
            )
            extracted_info.append(temp_string)

        for exp in results.get("education", {}) or {}:
            school = exp.get("school", "N/A")
            degree = exp.get("degree", "N/A")
            start = exp.get("start", "N/A").split("T")[0] if exp.get("start") else "N/A"
            end = exp.get("end", "Present") if exp.get("end") else "Present"
            major = exp.get("major", "N/A")

            if end != "Present":
                end = end.split("T")[0]

            extracted_info.append(f"{degree} in {major} at {school} ({start} - {end})")

        extracted_info.append(f"Skilled in {results.get('skills', 'N/A')}")

        extracted_information = "\n".join(extracted_info)
        explanation += extracted_information

        messages = [
            {
                "role": "user",
                "content": SUMMARY_PROMPT
                + f"\n<Information>\n{explanation}\n</Information>\n<User_Prompt>\n{main_query}\n</User_Prompt>",
            }
        ]
        summary = await claude(messages, model="claude-3-5-haiku-latest")
        if summary.get("summary", ""):
            return summary.get("summary", "")
        return ""
    else:
        return ""
