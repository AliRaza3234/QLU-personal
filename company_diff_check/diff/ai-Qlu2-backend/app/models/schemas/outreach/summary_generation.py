from pydantic import BaseModel
from typing import Dict, Optional


class SummaryRequest(BaseModel):
    profileData: Dict
    reference_message: Optional[str] = ""


class SummaryResponse(BaseModel):
    result: str
