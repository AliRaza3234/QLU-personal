from pydantic import BaseModel
from typing import Dict, Optional


class GenerateMetricsRequest(BaseModel):
    """Class for input payload"""

    text: str
    category: str


class GenerateMetricsResponse(BaseModel):
    """Class for output payload"""

    result: Dict[str, str]
