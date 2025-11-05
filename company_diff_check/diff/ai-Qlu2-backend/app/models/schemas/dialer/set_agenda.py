from pydantic import BaseModel
from typing import List, Dict, Any


class AgendaSetterRequest(BaseModel):
    text: str


class AgendaSetterResponse(BaseModel):
    data: Dict[str, Any]
    intent: str
