from pydantic import BaseModel


class FunctionsCountPayload(BaseModel):
    universal_name: str


class FunctionsCountResponse(BaseModel):
    output: dict


class FunctionsProfilesPayload(BaseModel):
    universal_name: str
    function: str
    offset: int
    limit: int


class FunctionsProfilesResponse(BaseModel):
    output: list
