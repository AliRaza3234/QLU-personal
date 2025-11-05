from fastapi import APIRouter

from app.routes.functions.post_counts_functions import router as function_count_router
from app.routes.functions.post_profiles_functions import (
    router as function_profile_router,
)

router = APIRouter()

router.include_router(function_count_router, prefix="/functions")
router.include_router(function_profile_router, prefix="/functions")
