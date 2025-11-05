from pydantic import BaseModel


class EvalHallucinationRequest(BaseModel):
    gen_text: str
    ref_text: str
    profile_summary: str


class EvalHallucinationResponse(BaseModel):
    result: str
