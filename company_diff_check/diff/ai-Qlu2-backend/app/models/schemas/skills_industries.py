from pydantic import BaseModel


class SkillAndIndustry(BaseModel):
    skills: list
    industries: list


class SkillAndIndustryOutput(BaseModel):

    skills: dict
    industries: dict
