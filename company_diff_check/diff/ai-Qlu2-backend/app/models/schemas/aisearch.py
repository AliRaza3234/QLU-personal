from pydantic import BaseModel, model_validator
from typing import Optional, Literal


class FinalAISearch(BaseModel):
    """Request body for the ai search"""

    query: str
    isDemographicsBlocked: Optional[bool] = False
    testing: Optional[bool] = False


class ExpansionAISearch(BaseModel):
    """Request body for the ai search"""

    context: dict
    oldQueries: list


class VariantsAISearch(BaseModel):
    """Request body for the ai search"""

    context: dict
    oldQueries: list


class AISearchRequest(BaseModel):
    """Request body for the ai search"""

    text: str
    filter_type: str
    ner_output: dict

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
                "school",
                "ownership",
                "company_tenure",
                "role_tenure",
                "gender",
                "ethnicity",
                "age",
            ]
        )
        if self.filter_type.lower() not in allowed_values:
            raise ValueError(f"filter_type must be one of {allowed_values}")
        return self


class AISearchNERRequest(BaseModel):
    """Request body for the ai search ner"""

    text: str
    type: str

    @model_validator(mode="after")
    def validate_filter_type(self):
        allowed_values = set(["role", "property"])
        if self.type.lower() not in allowed_values:
            raise ValueError(f"filter_type must be one of {allowed_values}")
        return self


class AISearchRefinePromptsRequest(BaseModel):
    """Request body for AI Search refine prompts service"""

    text: str


class FastModeQuery(BaseModel):
    """Request body for AI Search refine prompts service"""

    query: str
    conversation_id: str
    prompt_id: int
    isDemographicsBlocked: Optional[bool] = False
    visible_profiles: Optional[list] = []
    bakchodi: Optional[bool] = False


class MappedPersonQuery(BaseModel):
    """Request body for AI Search refine prompts service"""

    response_id: int
    conversation_id: str
    prompt_id: int
    reason: Literal[
        "update_identifier",
        "filters",
        "variants",
        "expansion",
        "profile_count",
        "suggestions",
        "manual_suggestions",
    ] = "update_identifier"
    manual: Optional[bool] = False
    identifier: Optional[str] = None
    prompt: Optional[str] = None
    filters: Optional[dict] = None  # or adjust type if it's not a string
    profile_count: Optional[int] = -1
