from pydantic import BaseModel


class FlagsPayload(BaseModel):
    esIds: list


class FlagsResponse(BaseModel):
    peopleOrgchartFlag: dict
