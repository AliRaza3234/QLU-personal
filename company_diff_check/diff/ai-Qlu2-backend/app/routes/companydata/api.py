from fastapi import APIRouter

from app.routes.companydata.post_news import router as news_api
from app.routes.companydata.post_stocks import router as stocks_api
from app.routes.companydata.post_summary import router as summary_api
from app.routes.companydata.post_reports import router as reports_api
from app.routes.companydata.post_products import router as products_api

from app.routes.companydata.post_financialdata import router as financials_api
from app.routes.companydata.get_cburl import router as cb_api
from app.routes.companydata.post_merger_acquisitions import router as mna_api
from app.routes.companydata.post_funding_filter import router as funding_filter_api
from app.routes.companydata.post_company_ownership_filter import (
    router as post_company_ownership_filter_api,
)
from app.routes.companydata.post_private_companies_data import (
    router as private_companies_api,
)

router = APIRouter()

router.include_router(financials_api, prefix="/companydata")
router.include_router(post_company_ownership_filter_api, prefix="/companydata")
router.include_router(news_api, prefix="/companydata")
router.include_router(stocks_api, prefix="/companydata")
router.include_router(summary_api, prefix="/companydata")
router.include_router(reports_api, prefix="/companydata")
router.include_router(products_api, prefix="/companydata")
router.include_router(private_companies_api, prefix="/companydata")
router.include_router(cb_api, prefix="/companydata")
router.include_router(mna_api, prefix="/companydata")
router.include_router(funding_filter_api, prefix="/companydata")
