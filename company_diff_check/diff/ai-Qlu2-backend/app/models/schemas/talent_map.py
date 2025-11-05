from pydantic import BaseModel, Field


class TalentMapSalInput(BaseModel):
    payload: dict


class TalentMapSalOutput(BaseModel):
    result: dict
