from pydantic import BaseModel
from typing import Optional


class SkillsDomainsInput(BaseModel):
    esId: str
    type: str
    version: Optional[str] = ""


class SkillsDomainsOutput(BaseModel):
    output: dict
