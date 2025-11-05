import asyncio
from app.core.database import postgres_fetch_all


async def skills_and_industry_counter(payload):
    skills = payload["skills"]
    industries = payload["industries"]

    tasks = []
    skill_counts = {}
    industry_counts = {}

    if skills:
        skill_name_mapping = {
            skill.lower().strip(): skill.lower().strip().title() for skill in skills
        }
        skill_conditions = " AS skill_name UNION SELECT ".join(
            [f"'{skill.lower().strip()}'" for skill in skills]
        )
        skill_query = f"""
    SELECT s.skill_name, COALESCE(SUM(sc.count), 0) AS total
        FROM (
            SELECT {skill_conditions} AS skill_name
        ) AS s
        LEFT JOIN skills_count_restructured AS sc ON s.skill_name = sc.skill_name
        GROUP BY s.skill_name;
        """
        tasks.append(postgres_fetch_all(skill_query))
    else:
        tasks.append(None)

    if industries:
        industry_name_mapping = {
            industry.lower().strip(): industry.lower().strip().title()
            for industry in industries
        }
        industry_conditions = " AS industry_name UNION SELECT ".join(
            [f"'{industry.lower().strip()}'" for industry in industries]
        )
        industry_query = f"""
    SELECT s.industry_name, COALESCE(SUM(sc.count), 0) AS total
        FROM (
            SELECT {industry_conditions} AS industry_name
        ) AS s
        LEFT JOIN industry_count_restructured AS sc ON s.industry_name = sc.industry_name
        GROUP BY s.industry_name;
        """
        tasks.append(postgres_fetch_all(industry_query))
    else:
        tasks.append(None)

    counts = await asyncio.gather(*[task for task in tasks if task is not None])
    if skills:
        skill_counts = {skill_name_mapping[skill[0]]: skill[1] for skill in counts[0]}
    if industries:
        index = 1 if skills else 0
        industry_counts = {
            industry_name_mapping[industry[0]]: industry[1]
            for industry in counts[index]
        }

    result = {"skills": skill_counts, "industries": industry_counts}
    return result
