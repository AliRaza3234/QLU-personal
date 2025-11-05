from pydantic import BaseModel, Field
from typing import Optional


class ShortenPromptInput(BaseModel):
    """Request body for the shorten prompt"""

    prompt: str = Field(..., min_length=1)
    agent: str = None


class ShortenPromptOutput(BaseModel):
    """Response body for the shorten prompt"""

    shortened_prompt: str


class DualShortenPromptOutput(BaseModel):
    """Response body for the dual shorten prompt"""

    current: Optional[str]
    past: Optional[str]
    timeline: Optional[str]


class ClusterCompaniesInput(BaseModel):
    """Request body for the Cluster Companies list"""

    prompt: str = Field(..., min_length=2)
    companies: list[str] = Field(default_factory=list)


class ClusterCompaniesOutput(BaseModel):
    """Response body for the Cluster Companies list"""

    refined_prompt: str
