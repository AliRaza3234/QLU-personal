from pydantic import BaseModel


class MapLocationRequest(BaseModel):
    """Request body for company financial filters"""

    locality: str
    locationName: str


class MapLocationResponse(BaseModel):
    """Response body for company financial filters"""

    metro_areas: str = None
    time_zone: str = None
    location_continent: str = None
    locationFullPath: str = None
