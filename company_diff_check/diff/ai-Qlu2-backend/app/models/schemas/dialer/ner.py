from pydantic import BaseModel
from typing import List, Dict, Any


class NEROnTextRequest(BaseModel):
    text: str


class NEROnTextResponse(BaseModel):
    result: Dict[str, Any]
