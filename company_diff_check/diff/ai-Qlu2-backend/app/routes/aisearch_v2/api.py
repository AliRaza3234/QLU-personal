from fastapi import APIRouter

from app.routes.aisearch_v2.post_final_aisearch import router as ai_search_router
from app.routes.aisearch_v2.post_expansion import router as ai_search_expansion
from app.routes.aisearch_v2.post_variants import router as ai_search_variants
from app.routes.aisearch_v2.fastmode import router as fastmode_router

router = APIRouter()

router.include_router(ai_search_variants, prefix="/aisearch")
router.include_router(ai_search_router, prefix="/aisearch")
router.include_router(ai_search_expansion, prefix="/aisearch")
router.include_router(ai_search_router, prefix="/aisearch")
router.include_router(fastmode_router, prefix="/aisearch_fastmode")
