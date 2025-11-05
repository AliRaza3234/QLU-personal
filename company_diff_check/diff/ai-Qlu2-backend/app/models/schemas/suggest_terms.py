from pydantic import BaseModel


class SuggestTermsInput(BaseModel):
    entity: str
    entity_type: str


class SuggestTermsOutput(BaseModel):
    suggested_terms: list[str]
