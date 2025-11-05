from pydantic import BaseModel
from typing import List, Dict, Any


class SummaryGeneratorRequest(BaseModel):
    transcriptions: list


class SummaryGeneratorResponse(BaseModel):
    result: Dict[str, str]
