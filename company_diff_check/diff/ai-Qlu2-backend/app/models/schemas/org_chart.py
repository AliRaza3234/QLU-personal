from pydantic import BaseModel, Field
from typing import Optional


class OrgChartRequest(BaseModel):
    universalName: str


class OrgChartResponse(BaseModel):
    output: Optional[dict] = None


# class PeopleOrgChartRequest(BaseModel):
#     es_id: str


# class PeopleOrgChartResponse(BaseModel):
#     output: Optional[dict] = None


class PeopleOrgRequest(BaseModel):
    """Request body for the people org chart generation"""

    id: str = Field(..., min_length=2)


class PeopleOrgResponse(BaseModel):
    """Response body for the people org chart generation"""

    output: dict
