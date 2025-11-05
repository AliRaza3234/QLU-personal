from pydantic import BaseModel


class MiniatureRoundIn(BaseModel):
    es_id: str
    call_pitch: str
    channel: str


class MiniatureRoundOut(BaseModel):
    message: dict
