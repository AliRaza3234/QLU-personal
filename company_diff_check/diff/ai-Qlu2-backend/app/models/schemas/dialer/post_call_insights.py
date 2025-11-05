from pydantic import BaseModel
from typing import List, Dict, Any


class PostCallInsightsRequest(BaseModel):
    transcriptions: List[Dict[str, Any]]
    pitch: str


class PostCallInsightsResponse(BaseModel):
    isInterested: bool
    isFollowup: bool
    isPitched: bool
