from pydantic import BaseModel
from typing import Dict, Any


class ProfileSummaryRequest(BaseModel):
    profileEsID: str


class ProfileSummaryResponse(BaseModel):
    result: str
