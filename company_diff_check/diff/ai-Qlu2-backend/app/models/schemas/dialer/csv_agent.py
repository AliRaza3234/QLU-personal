from typing import Dict
from pydantic import BaseModel


class CSVProcessingResponse(BaseModel):
    resul: Dict[str, str]
