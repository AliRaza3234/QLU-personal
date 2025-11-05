import traceback
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.models.schemas.name_search import nameSearch
from app.utils.name_search.search import main as search

router = APIRouter()


@router.post("/name_search")
async def service_flags(request: nameSearch):
    query = request.query
    try:
        response = await search(query)
        return JSONResponse({"result": response})
    except Exception as e:
        traceback.print_exc()
        error_trace = traceback.format_exc()
        return JSONResponse(content={"message": "Error"}, status_code=500)
