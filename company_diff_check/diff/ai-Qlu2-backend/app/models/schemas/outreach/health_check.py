from pydantic import BaseModel


class HealthCheckResponse(BaseModel):
    """Class for output payload"""

    result: str
