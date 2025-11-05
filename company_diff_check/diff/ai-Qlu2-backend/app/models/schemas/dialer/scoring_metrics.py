from pydantic import BaseModel
from typing import Dict


class ScoreRequest(BaseModel):
    text: str
    metrices: Dict[str, str]


class ScoreResponse(BaseModel):
    scores: Dict[str, str]
    tooltips: Dict[str, str]
