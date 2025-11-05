from pydantic import BaseModel


class DecisionMakerRequest(BaseModel):
    email: str
    subject: str
