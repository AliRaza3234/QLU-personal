import traceback
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.routes.dependancies import get_es_client
from app.models.schemas.aisearch import VariantsAISearch
from app.utils.aisearch_expansion_variants.variants import variants
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/variants")
async def ai_search_variants(
    input_payload: VariantsAISearch, es_client=Depends(get_es_client)
):
    context = input_payload.context
    queries = input_payload.oldQueries

    try:
        response = await variants(context, queries, es_client)
        return JSONResponse({"result": response})
    except Exception as e:
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=input_payload.dict(),
            route="/aisearch/variants",
            service_name="AISEARCH",
        )
        return JSONResponse(content={"message": "Error"}, status_code=500)
