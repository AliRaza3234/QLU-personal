from pydantic import BaseModel


class RouterRequest(BaseModel):
    text: str


class RouterResponse(BaseModel):
    result: str
