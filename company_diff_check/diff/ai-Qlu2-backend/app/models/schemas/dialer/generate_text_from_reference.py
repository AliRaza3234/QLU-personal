from pydantic import BaseModel
from typing import Dict, Optional, List


class generateSampleRequest(BaseModel):
    """Class for input payload"""

    reference: str
    category: str
    profileEsID: str
    sender_name: str


class generateTextRequest(BaseModel):
    """Class for input payload"""

    text: List[str]
    reference: str
    subject: Optional[str] = ""
    channel: str
    profileData: dict
    sender_name: str
    receiver_name: str
    category: str
    companies: str
    contact: str
    links: str
    profileSummary: str
    isPersonalised: bool
    placeholderReference: str


class generateTextResponse(BaseModel):
    """Class for output payload"""

    result: Dict[str, Dict[str, Optional[str]]]
