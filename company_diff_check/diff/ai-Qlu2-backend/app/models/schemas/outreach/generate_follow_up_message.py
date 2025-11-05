from pydantic import BaseModel
from typing import Dict, Optional, Any, List


class FollowupRequest(BaseModel):
    text: List[str]
    channel: str
    sender_name: str
    receiver_name: str
    reference: Optional[str] = ""
    profileData: Dict[str, Any]


class FollowupResponse(BaseModel):
    result: Dict[str, Dict[str, Optional[str]]]
