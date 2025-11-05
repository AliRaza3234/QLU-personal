from pydantic import BaseModel
from typing import Dict


class LivePitchRequest(BaseModel):
    text: str


class LivePitchResponse(BaseModel):
    result: Dict[str, str]
