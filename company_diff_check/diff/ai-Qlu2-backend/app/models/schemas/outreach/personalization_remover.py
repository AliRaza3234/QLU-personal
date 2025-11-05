from pydantic import BaseModel


class PersonalizationRequest(BaseModel):
    text: str


class PersonalizationResponse(BaseModel):
    result: str
