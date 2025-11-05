from typing import Dict, Optional
from pydantic import BaseModel


class EnhanceRequest(BaseModel):
    text: str
    attributes: dict
    sender_name: str
    category: str
    channel: str
    auto_enhance: Optional[bool] = False


class EnhanceResponse(BaseModel):
    result: Dict[str, Dict[str, Optional[str]]]
