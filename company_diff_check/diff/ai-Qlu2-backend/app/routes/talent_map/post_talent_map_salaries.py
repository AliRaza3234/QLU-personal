import traceback
from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from fastapi import Depends

from app.routes.dependancies import get_es_client
from app.routes.dependancies import get_db_client

from app.models.schemas.talent_map import TalentMapSalInput, TalentMapSalOutput

from app.utils.search.qsearch.tmap.salary import Calculations
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/salary", response_model=TalentMapSalOutput)
async def final_salary_updates(
    request: TalentMapSalInput,
    background_task: BackgroundTasks,
    es_client=Depends(get_es_client),
    db_client=Depends(get_db_client),
):
    payload = request.payload
    output = {}
    try:
        salary = await Calculations(payload, es_client, background_task, db_client)
        output = salary

    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request.dict(),
            route="/talent_map/salary",
            service_name="TALENT MAP",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})

    output = TalentMapSalOutput(result=output)
    return output
