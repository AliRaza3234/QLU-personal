from pydantic import BaseModel, Field


class CheckRequest(BaseModel):
    """Product Data request model"""

    user_query: str = Field(..., description="User Query")
    prompt: str = Field(..., description="Prompt")
