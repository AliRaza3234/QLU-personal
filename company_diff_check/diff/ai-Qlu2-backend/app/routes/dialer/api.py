from fastapi import APIRouter

from app.routes.dialer.post_summary import router as summary_gen_api
from app.routes.dialer.post_ner import router as ner_text_api
from app.routes.dialer.post_gen_scores import router as gen_scores_api
from app.routes.dialer.post_enhance_pitch import router as enhance_pitch_api
from app.routes.dialer.post_gen_custom_pitch import router as gen_custom_pitch_api
from app.routes.dialer.post_callee_interest import router as callee_interest_api
from app.routes.dialer.post_csv_agent import router as csv_agent_api
from app.routes.dialer.post_call_insights import router as post_call_insights_api
from app.routes.dialer.post_voicemial_transcript import (
    router as voicemail_transcript_api,
)

router = APIRouter()
router.include_router(summary_gen_api, prefix="/dialer")
router.include_router(ner_text_api, prefix="/dialer")
router.include_router(gen_scores_api, prefix="/dialer")
router.include_router(enhance_pitch_api, prefix="/dialer")
router.include_router(gen_custom_pitch_api, prefix="/dialer")
router.include_router(callee_interest_api, prefix="/dialer")
router.include_router(csv_agent_api, prefix="/dialer")
router.include_router(post_call_insights_api, prefix="/dialer")
router.include_router(voicemail_transcript_api, prefix="/dialer")
