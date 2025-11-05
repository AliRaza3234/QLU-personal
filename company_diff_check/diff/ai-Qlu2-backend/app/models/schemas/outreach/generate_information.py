from pydantic import BaseModel
from typing import Dict


class generateInfomrationRequest(BaseModel):
    """Class for input payload"""

    reference: str
    profileData: dict


class generateInformationResponse(BaseModel):
    """Class for output payload"""

    result: Dict[str, str]
