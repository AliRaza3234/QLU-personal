from pydantic import BaseModel
from typing import Optional


class EvaluationPayload(BaseModel):
    newQuery: str
    oldQueries: list
    isDemographicsBlocked: Optional[bool] = False


class ResponseEvaluationPayload(BaseModel):
    result: dict


class ModificationPayload(BaseModel):
    newQuery: str
    context: list
    entity: str


class ResponseModificationPayload(BaseModel):
    result: dict
