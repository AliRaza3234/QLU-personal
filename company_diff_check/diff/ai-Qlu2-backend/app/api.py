from fastapi import APIRouter

from app.routes.name_search import router as name_search_api
from app.routes.post_salary import router as salary_api
from app.routes.companydata.api import router as companydata_api
from app.routes.post_autocomplete import router as autocomplete_api
from app.routes.post_company_competitors import router as company_competitors_api
from app.routes.post_demographics import router as demographics_api
from app.routes.post_location_mapping import router as location_mapping_api
from app.routes.post_skills_domains import router as skills_domains_api
from app.routes.post_skills_industries import router as skills_industries_api
from app.routes.post_company_generation import router as company_generation_api
from app.routes.post_company_evaluation import router as company_evaluation_api
from app.routes.post_shorten_prompt import router as shorten_prompt_api
from app.routes.post_suggest_terms import router as suggest_terms_api
from app.routes.get_similar_profiles_extension import (
    router as similar_profiles_extension,
)
from app.routes.post_group_revenue import router as group_revenue_api
from app.routes.outreach.api import router as outreach_api
from app.routes.post_etl_functional_area import router as etl_functional_areas_api
from app.routes.groups.api import router as groups_api
from app.routes.ranks.api import router as ranks_api
from app.routes.functions.api import router as functions_api
from app.routes.businessunits.api import router as businessunits_api
from app.routes.aisearch_v2.api import router as aisearch_api
from app.routes.ai_search_context.api import router as aisearch_context_api
from app.routes.reports.api import router as reports_api
from app.routes.talent_map.api import router as talentmap
from app.routes.dialer.api import router as dialer_api
from app.routes.post_similar_profiles import router as similar_profiles
from app.routes.products.post_product_summary import router as product_summary
from app.routes.products.post_product_data import router as product_data
from app.routes.products.post_product_competitor import router as product_competitor
from app.routes.products.post_company_products import router as company_products
from app.routes.products.post_prod_checking import router as product_check
from app.routes.industry_NER import router as industry_NER


router = APIRouter()

router.include_router(industry_NER)
router.include_router(name_search_api)
router.include_router(aisearch_context_api)
router.include_router(talentmap)
router.include_router(companydata_api)
router.include_router(salary_api)
router.include_router(autocomplete_api)
router.include_router(company_competitors_api)
router.include_router(demographics_api)
router.include_router(location_mapping_api)
router.include_router(skills_domains_api)
router.include_router(skills_industries_api)
router.include_router(company_generation_api)
router.include_router(company_evaluation_api)
router.include_router(shorten_prompt_api)
router.include_router(aisearch_api)
router.include_router(suggest_terms_api)
router.include_router(group_revenue_api)
router.include_router(outreach_api)
router.include_router(etl_functional_areas_api)
router.include_router(groups_api)
router.include_router(ranks_api)
router.include_router(functions_api)
router.include_router(businessunits_api)
router.include_router(reports_api)
router.include_router(dialer_api, tags=["dialer"])
router.include_router(similar_profiles)
router.include_router(similar_profiles_extension)
router.include_router(product_summary)
router.include_router(product_data)
router.include_router(product_competitor)
router.include_router(company_products)
router.include_router(product_check)
