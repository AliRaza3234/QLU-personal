from fastapi import APIRouter

from app.routes.ranks.post_counts_ranks import router as rank_count_router
from app.routes.ranks.post_profiles_ranks import router as rank_profile_router

router = APIRouter()

router.include_router(rank_count_router, prefix="/ranks")
router.include_router(rank_profile_router, prefix="/ranks")
