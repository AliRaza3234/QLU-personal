from pydantic import BaseModel
from typing import Dict, List, Optional


class SentimentRequest(BaseModel):
    # context: Optional[str] = ""
    # text: Optional[str] = ""
    # texts: Optional[List[Dict[str, str]]] = []
    texts: List[Dict[str, str]]


class SentimentResponse(BaseModel):
    result: Dict[str, str]
