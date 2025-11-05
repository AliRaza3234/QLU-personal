from pydantic import BaseModel
from typing import Dict, Optional, List


class generateSampleRequest(BaseModel):
    """Class for input payload"""

    text: List[str]
    reference: str
    subject: Optional[str] = ""
    channel: str  # [{channel: 'email', number: 1},...],
    profileData: dict
    sender_name: str
    receiver_name: str
    category: str


class generateTextRequest(BaseModel):
    """Class for input payload"""

    text: List[str]
    reference: str
    subject: Optional[str] = ""
    channel: str  # [{channel: 'email', number: 1},...],
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
    isEducation: Optional[bool] = False


class generateMassTextRequest(BaseModel):
    """Class for input payload"""

    text: List[str]
    references: List[str]
    subjects: Optional[List[str]] = []
    channels: List[str]  # [{channel: 'email', number: 1},...],
    profileData: dict
    sender_names: List[str]
    receiver_name: str
    category: str
    companies: List[str]
    contacts: List[str]
    links: List[str]
    profileSummary: str
    isPersonalised: List[bool]
    placeholderReferences: List[str]
    isEducation: Optional[List[bool]] = []


class generateTextResponse(BaseModel):
    """Class for output payload"""

    result: Dict[str, Dict[str, Optional[str]]]
