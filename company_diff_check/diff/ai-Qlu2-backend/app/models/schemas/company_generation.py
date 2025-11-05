from pydantic import BaseModel, Field, model_validator
from typing import Optional, List


class Company(BaseModel):
    """Detailed company information model"""

    li_name: str = Field(..., description="Company name")
    li_universalname: str = Field(..., description="Universal company name")
    es_id: str = Field(..., description="Elasticsearch identifier")
    li_urn: str = Field(..., description="Company urn")
    li_industries: str = Field(..., description="Company Industries")


class CompanyGenerationRequest(BaseModel):
    """Class for input payload"""

    prompt: Optional[str] = ""
    current_prompt: Optional[str] = ""
    past_prompt: Optional[str] = ""
    userquery: Optional[str] = ""
    context: list[dict] = Field(default_factory=list)
    companies: Optional[List[Company]] = ""
    description: Optional[bool] = False
    employee_count: Optional[dict] = Field(default_factory=dict)
    company_ownership: Optional[list] = Field(default_factory=list)
    product_filter: Optional[bool] = False
    agent: str = "semi-expert"

    @model_validator(mode="after")
    def agent_must_be_valid(self):
        """Validate financial type"""
        if self.agent not in [
            "semi-expert",
            "aisearch",
            "dual",
            "product_filter",
            "product_aisearch",
        ]:
            raise ValueError(
                "Agent must be semi-expert, aisearch, dual, product_filter, or product_aisearch"
            )
        return self


class PromptSuggestionsRequest(BaseModel):
    """Class for input payload"""

    prompt: str = Field(..., min_length=2)


class P2PScoringRequest(BaseModel):
    """Class for P2P Scoring Request payload"""

    prompt: str = Field(..., min_length=2)
    companies: list[str]


class P2PScoringResponse(BaseModel):
    """Class for P2P Scoring Response payload"""

    scores: dict[str, int]
