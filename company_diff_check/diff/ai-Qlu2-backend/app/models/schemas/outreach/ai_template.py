from pydantic import BaseModel
from typing import List, Optional


class AIGenCampaignResponse(BaseModel):
    data: List[dict]


class AIGenCampaignRequest(BaseModel):
    assignment_name: str
    total_profiles: int
    sample_profiles: List[str] = []
    channel_credits: dict
    creation_day: str
    override_sample: Optional[bool] = True
    profile_data: Optional[List[str]] = []
    sender_data: str = ""
