from pydantic import BaseModel


class IndustryNERInput(BaseModel):
    convId: str
    promptId: int
    text: str
    demoBlocked: bool
