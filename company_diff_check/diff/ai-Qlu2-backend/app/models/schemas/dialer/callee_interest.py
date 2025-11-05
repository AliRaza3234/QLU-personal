from typing import Dict, Optional
from pydantic import BaseModel


class CalleeInterestRequest(BaseModel):
    caller_transcription: list
    callee_transcription: list


class CalleeInterestResponse(BaseModel):
    result: str
