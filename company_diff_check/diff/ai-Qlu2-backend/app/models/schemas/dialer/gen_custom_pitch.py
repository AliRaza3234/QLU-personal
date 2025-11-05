from pydantic import BaseModel
from typing import Dict, Optional, Any


class GenCustomPitchRequest(BaseModel):
    """Class for input payload"""

    text: str
    callee_name: str
    callee_id: int


class GenCustomPitchResponse(BaseModel):
    """Class for output payload"""

    pitch: str
    callee_id: int
