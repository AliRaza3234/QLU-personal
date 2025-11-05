from pydantic import BaseModel, Field, model_validator


class AISearchRequest(BaseModel):
    """Request body for the ai search"""

    text: str
    filter_type: str

    @model_validator(mode="after")
    def validate_filter_type(self):
        allowed_values = set(
            [
                "name",
                "title",
                "location",
                "industry",
                "skill",
                "education",
                "experience",
                "management_level",
                "institution",
            ]
        )
        if self.filter_type.lower() not in allowed_values:
            raise ValueError(f"filter_type must be one of {allowed_values}")
        return self


class AISearchSuggestedPrompts(BaseModel):
    """Request body for suggested prompts service"""

    query: str


class AISearchChildPromptsRequest(BaseModel):
    """Request body for child prompts service"""

    prompt: str


class AISearchChildPromptsResponse(BaseModel):
    """Response body for child prompts service"""

    child_prompts: list[str]
