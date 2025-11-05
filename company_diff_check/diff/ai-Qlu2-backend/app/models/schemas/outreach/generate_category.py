from pydantic import BaseModel
from typing import Dict, Optional


class GenerateCategoryRequest(BaseModel):
    """Class for input payload"""

    text: str


class GenerateCategoryResponse(BaseModel):
    """Class for output payload"""

    result: str
