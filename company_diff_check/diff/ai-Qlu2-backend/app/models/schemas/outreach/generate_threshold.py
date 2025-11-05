from pydantic import BaseModel
from typing import Dict


class GenerateThresholdRequest(BaseModel):
    """Class for input payload"""

    category: str
    metrics: Dict[str, str]


class GenerateThresholdResponse(BaseModel):
    """Class for output payload"""

    result: Dict[str, str]
