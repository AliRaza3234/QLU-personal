from pydantic import BaseModel, Field


class DataRequest(BaseModel):
    """Company Products request model"""

    li_universalname: str = Field(..., description="Company Identifier")
    li_name: str = Field(..., description="Company Name")
    es_id: str = Field(..., description="Company es_id")
