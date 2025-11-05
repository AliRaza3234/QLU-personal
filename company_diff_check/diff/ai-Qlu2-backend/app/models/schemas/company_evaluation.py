from pydantic import BaseModel, Field
from typing import Dict, Any


class CompanyEvaluationRequest(BaseModel):
    """Class for input payload for evaluation"""

    prompt: str = Field(..., min_length=2)
    company: Dict[str, Any]


class VerifyRequest(BaseModel):
    """Class for input payload for verification of keypoints"""

    prompt: str = Field(..., min_length=2)
