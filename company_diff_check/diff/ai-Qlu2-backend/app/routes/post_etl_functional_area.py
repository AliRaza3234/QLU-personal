import traceback
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.models.schemas.etl_functional_areas import (
    EtlFunctionalAreasRequest,
    EtlFunctionalAreasResponse,
)
from app.utils.etl.functional_areas import get_functional_area


router = APIRouter()


@router.post("/etl_functional_areas")
async def map_functional_areas(request: EtlFunctionalAreasRequest):
    try:
        response = await get_functional_area(request)
        return EtlFunctionalAreasResponse(**{"function": response})
    except Exception as e:
        print("Exception: ", e)
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
