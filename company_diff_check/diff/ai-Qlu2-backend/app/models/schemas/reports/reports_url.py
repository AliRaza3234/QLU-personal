from typing import Dict, Optional, Any
from pydantic import BaseModel


class ReportURLResponse(BaseModel):
    signed_url: Optional[str] = None
