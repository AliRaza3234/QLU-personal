from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.models.schemas.outreach.decision_maker import (
    DecisionMakerRequest,
)

from app.utils.outreach.utils.gpt_utils.gpt_utils import check_subject_personalization

import traceback

router = APIRouter()


@router.post("/decision_maker")
async def decision_maker(
    request: DecisionMakerRequest,
):
    try:
        decision = await check_subject_personalization(request.subject, request.email)
        return JSONResponse(status_code=200, content=decision)
    except Exception as e:
        error_trace = traceback.format_exc()
        raise HTTPException(
            status_code=500, detail={"error": str(e), "traceback": error_trace}
        )
