from pydantic import BaseModel
from typing import List, Dict, Any


class AgendaCheckerRequest(BaseModel):
    agenda_input: Dict[str, Any]
    outbound_list: List[str]
    inbound_list: List[str]


class AgendaCheckerResponse(BaseModel):
    result: Dict[str, Any]
