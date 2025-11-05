from fastapi import APIRouter

from app.routes.outreach.post_enhance_text import router as enhance_text_api
from app.routes.outreach.post_get_miniature_round import router as miniature_round_api
from app.routes.outreach.post_decision_maker import router as decision_maker_api
from app.routes.outreach.post_gen_from_text_reference import router as gen_text_api
from app.routes.outreach.post_modify_response import router as modify_resp_api
from app.routes.outreach.post_converse import router as converse_api
from app.routes.outreach.post_gen_scores import router as scoring_metric_api
from app.routes.outreach.post_gen_category import router as gen_category_api
from app.routes.outreach.post_gen_metrics import router as gen_metrics_api
from app.routes.outreach.post_sentiment_analysis import router as sentiment_analysis_api
from app.routes.outreach.post_summary_generation import router as summary_generation_api
from app.routes.outreach.get_health_check import router as health_check_api
from app.routes.outreach.post_gen_sample_follow_up import router as sample_followup_api
from app.routes.outreach.post_gen_sample_from_text_reference import (
    router as sample_gen_text,
)
from app.routes.outreach.post_gen_information import router as gen_information_api

from app.routes.outreach.post_ai_template import router as ai_gen_template_api

router = APIRouter()

router.include_router(enhance_text_api, prefix="/outreach")
router.include_router(gen_text_api, prefix="/outreach")
router.include_router(modify_resp_api, prefix="/outreach")
router.include_router(gen_category_api, prefix="/outreach")
router.include_router(gen_metrics_api, prefix="/outreach")
router.include_router(scoring_metric_api, prefix="/outreach")
router.include_router(sentiment_analysis_api, prefix="/outreach")
router.include_router(summary_generation_api, prefix="/outreach")
router.include_router(health_check_api, prefix="/outreach")
router.include_router(sample_followup_api, prefix="/outreach")
router.include_router(sample_gen_text, prefix="/outreach")
router.include_router(gen_information_api, prefix="/outreach")
router.include_router(ai_gen_template_api, prefix="/outreach_2")
router.include_router(miniature_round_api, prefix="/outreach")
router.include_router(decision_maker_api, prefix="/outreach")
router.include_router(converse_api, prefix="/outreach")
