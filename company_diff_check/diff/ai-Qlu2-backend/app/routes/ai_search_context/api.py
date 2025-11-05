from fastapi import APIRouter

from app.routes.ai_search_context.context import router as ai_search_context_router

router = APIRouter()

router.include_router(ai_search_context_router, prefix="/aisearch_context")
