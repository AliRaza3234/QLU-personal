from pydantic import BaseModel, Field


class SalaryInput(BaseModel):
    esId: str = Field(..., min_length=2)


class SalaryOutput(BaseModel):
    result: dict
