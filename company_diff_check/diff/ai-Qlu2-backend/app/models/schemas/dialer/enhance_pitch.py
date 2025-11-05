from typing import Dict, Optional
from pydantic import BaseModel


class EnhanceRequest(BaseModel):
    text: str
    metrices: dict
    caller_name: str
    callee_name: str


class EnhanceResponse(BaseModel):
    result: Dict[str, Dict[str, Optional[str]]]
