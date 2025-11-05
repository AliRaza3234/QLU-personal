from pydantic import BaseModel


class BusinessUnitsPayload(BaseModel):
    universal_name: str
    business_unit: str


class BusinessUnitsTracePayload(BaseModel):
    universal_name: str
    business_unit: str
    year: int
    period: int
    value: int
    container: list
