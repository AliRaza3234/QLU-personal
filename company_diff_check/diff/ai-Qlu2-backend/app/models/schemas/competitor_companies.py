from pydantic import BaseModel, Field


class CompanyCompetitorsRequest(BaseModel):
    """Request body for the company generation"""

    id: str = Field(..., min_length=2)


class CompanyCompetitorsResponse(BaseModel):
    """Response body for the company generation"""

    output: dict
