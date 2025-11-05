from pydantic import BaseModel


class RanksCountPayload(BaseModel):
    universal_name: str


class RanksCountResponse(BaseModel):
    output: dict


class RanksProfilesPayload(BaseModel):
    universal_name: str
    rank: str
    offset: int
    limit: int


class RanksProfilesResponse(BaseModel):
    output: list
