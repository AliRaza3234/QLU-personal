from typing import Optional
from pydantic import BaseModel, Field


class EtlFunctionalAreasRequest(BaseModel):
    title: Optional[str] = Field(None, description="Title from the latest experience")
    headline: Optional[str] = Field(None, description="Headline of the profile")
    universal_name: Optional[str] = Field(
        None, description="Universal Name of from the latest experience"
    )


class EtlFunctionalAreasResponse(BaseModel):
    function: Optional[str] = Field(None, description="Function of the profile")
