from fastapi import APIRouter

from app.routes.talent_map.post_talent_map_salaries import (
    router as talent_map_salary_api,
)

router = APIRouter()

router.include_router(talent_map_salary_api, prefix="/talent_map")
