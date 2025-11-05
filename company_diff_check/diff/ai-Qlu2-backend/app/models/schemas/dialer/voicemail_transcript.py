from pydantic import BaseModel
from typing import List, Dict, Any


class VoicemailAudioBufferRequest(BaseModel):
    # link: List[int]  # Array buffer as list of integers # link written because previous was getting link as str.
    link: Any


class VoicemailTranscripcResponse(BaseModel):
    result: Dict[str, Any]
