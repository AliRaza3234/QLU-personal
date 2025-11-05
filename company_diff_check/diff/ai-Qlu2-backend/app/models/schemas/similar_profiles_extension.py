from pydantic import BaseModel


class SimilarProfilesInput(BaseModel):
    esId: str
    type: str
    offset: int
    limit: int


class SimilarProfilesOutput(BaseModel):
    output: list
