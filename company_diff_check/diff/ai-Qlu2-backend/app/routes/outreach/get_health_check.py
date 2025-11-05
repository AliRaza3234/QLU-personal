from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.models.schemas.outreach.health_check import HealthCheckResponse

router = APIRouter()


@router.get("/", response_model=HealthCheckResponse)
def health_check():
    print("All good")
    return JSONResponse(status_code=200, content="All Good")
