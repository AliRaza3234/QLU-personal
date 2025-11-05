from pydantic import BaseModel
from typing import List, Dict, Any


class SimilarProfilesInput(BaseModel):
    esId: str
    type: str
    offset: int
    limit: int
    serviceType: str
    groups: str
    rank: str
    function: str
    filters: Dict[str, Any]
    peopleFilters: Dict[str, Any]
    experienceIndices: List[int] = None


class Profile(BaseModel):
    esId: str
    experienceIndex: int


class SimilarProfilesOutput(BaseModel):
    output: List[Profile]
    count: int
