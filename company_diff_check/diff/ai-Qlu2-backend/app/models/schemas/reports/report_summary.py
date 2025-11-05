from typing import Dict, Optional, Any
from pydantic import BaseModel


class ReportSummaryRequest(BaseModel):
    report_link: Optional[str] = None
    blob_name: str


class ReportSummaryResponse(BaseModel):
    result: Dict[str, Any]
