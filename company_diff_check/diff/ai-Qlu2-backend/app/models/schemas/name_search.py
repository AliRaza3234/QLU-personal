from pydantic import BaseModel


class nameSearch(BaseModel):
    query: str


class nameSearchResponse(BaseModel):
    people: list
