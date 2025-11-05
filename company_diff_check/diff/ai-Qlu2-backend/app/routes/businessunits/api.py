from fastapi import APIRouter

from app.routes.businessunits.post_bu_revenue_annually import (
    router as bu_revenue_yearly_api,
)
from app.routes.businessunits.post_bu_revenue_quarterly import (
    router as bu_revenue_quarterly_api,
)
from app.routes.businessunits.post_bu_names import router as bu_names_api
from app.routes.businessunits.post_bu_summary import router as bu_summary_api
from app.routes.businessunits.post_bu_trace import router as bu_trace_api

router = APIRouter()


router.include_router(bu_revenue_yearly_api, prefix="/businessunits")
router.include_router(bu_revenue_quarterly_api, prefix="/businessunits")
router.include_router(bu_names_api, prefix="/businessunits")
router.include_router(bu_summary_api, prefix="/businessunits")
router.include_router(bu_trace_api, prefix="/businessunits")
