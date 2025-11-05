from typing import List, Optional
from pydantic import BaseModel, Field


class Company(BaseModel):
    """Detailed company information model"""

    li_name: str = Field(..., description="Company name")
    li_universalname: str = Field(..., description="Universal company name")
    es_id: str = Field(..., description="Elasticsearch identifier")
    li_urn: str = Field(..., description="Company urn")
    li_industries: str = Field(..., description="Company Industries")


class ProductGenerationRequest(BaseModel):
    """Class for input payload"""

    companies: Optional[List[Company]] = ""
    prompt: Optional[str] = ""
    agent: Optional[str] = ""
