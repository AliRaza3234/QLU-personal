from fastapi import APIRouter

from app.routes.groups.post_subgroup_counts import router as sg_count_router
from app.routes.groups.post_subgroup_people_counts import (
    router as sg_count_funtion_rank_router,
)
from app.routes.groups.post_subgroup_people_profiles import (
    router as sg_profile_funtion_rank_router,
)

router = APIRouter()

router.include_router(sg_count_router, prefix="/groups")
router.include_router(sg_count_funtion_rank_router, prefix="/groups")
router.include_router(sg_profile_funtion_rank_router, prefix="/groups")
