from pydantic import BaseModel
from typing import Dict


class ScoreRequest(BaseModel):
    text: str
    category: str
    metrics: Dict[str, str]


class ScoreResponse(BaseModel):
    result: Dict[str, str]
