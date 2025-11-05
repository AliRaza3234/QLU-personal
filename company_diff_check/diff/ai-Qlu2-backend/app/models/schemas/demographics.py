from pydantic import BaseModel
from typing import Union


class DemographicsPayload(BaseModel):
    image_url: str
    esId: str
    education: list
    experience: list
    fullName: str
    firstName: str
    lastName: str


class DemographicsResponse(BaseModel):
    age: Union[int, None]
    gender: str
    race: str
