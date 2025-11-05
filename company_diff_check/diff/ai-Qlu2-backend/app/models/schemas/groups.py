from pydantic import BaseModel


class SubgroupCountsPayload(BaseModel):
    universal_name: str


class SubgroupCountsResponse(BaseModel):
    output: dict


class SubgroupFunctionAndRankCountsPayload(BaseModel):
    universal_name: str
    sub_group_name: str
    type: str


class SubgroupFunctionAndRankCountsResponse(BaseModel):
    output: dict


class SubgroupFunctionAndRankProfilesPayload(BaseModel):
    universal_name: str
    sub_group_name: str
    type: str
    filter: str
    offset: int
    limit: int


class SubgroupFunctionAndRankProfilesResponse(BaseModel):
    output: list
