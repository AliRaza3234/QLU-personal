from pydantic import BaseModel


class AISearchRequest(BaseModel):
    """Request body for the ai search"""

    text: str


class AISearchRequestV2(BaseModel):
    """Request body for the ai search"""

    text: str
    context: list[dict] = []


class AISearchResponse(BaseModel):
    """Response body for AI Search refine prompts service"""

    text: str
