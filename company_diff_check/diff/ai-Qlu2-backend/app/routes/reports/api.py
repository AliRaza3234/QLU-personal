from fastapi import APIRouter

from app.routes.reports.post_report_summary import router as report_summary_api
from app.routes.reports.post_report_data import router as report_data_api
from app.routes.reports.get_report_url import router as report_url_api

router = APIRouter()

router.include_router(report_summary_api, prefix="/reports")
router.include_router(report_data_api, prefix="/reports")
router.include_router(report_url_api, prefix="/reports")
