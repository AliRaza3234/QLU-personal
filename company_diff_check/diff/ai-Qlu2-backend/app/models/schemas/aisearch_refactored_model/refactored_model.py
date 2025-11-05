from pydantic import BaseModel


class Refactored(BaseModel):
    prompt: str


class RefactoredResponse(BaseModel):
    result: list
