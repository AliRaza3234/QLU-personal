from typing import Dict, Optional, Any
from pydantic import BaseModel


class ReportYearsRequest(BaseModel):
    li_universal_name: str


class ReportYearsResponse(BaseModel):
    result: dict
