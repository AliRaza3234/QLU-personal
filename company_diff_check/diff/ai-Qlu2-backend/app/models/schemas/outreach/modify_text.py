from pydantic import BaseModel
from typing import Dict


class ModifyTextRequest(BaseModel):
    text: str
    mod_type: str
    sender_name: str
    receiver_name: str
    channel: str


class ModifyTextResponse(BaseModel):
    result: Dict[str, Dict[str, str]]
