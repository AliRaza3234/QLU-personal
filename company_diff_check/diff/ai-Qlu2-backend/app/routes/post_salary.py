import traceback
from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse

from app.routes.dependancies import get_es_client
from app.routes.dependancies import get_db_client

from app.models.schemas.salary import SalaryInput, SalaryOutput
from qutils.slack.notifications import send_slack_notification
from app.utils.people.salary.person_salary import main as all_title_salary_final

router = APIRouter()


@router.post("/salary", response_model=SalaryOutput)
async def final_salary_updates(
    request: SalaryInput,
    background_task: BackgroundTasks,
    es_client=Depends(get_es_client),
    db_client=Depends(get_db_client),
):
    person_id = request.esId
    output = {}
    try:
        salary = await all_title_salary_final(
            person_id, background_task, es_client, db_client
        )
        if "message" in salary.keys():
            return JSONResponse(
                status_code=500, content={"message": f"Error 'User not found'"}
            )
        output = salary

    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=person_id,
            route="/salary",
            service_name="SALARY",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})

    output = SalaryOutput(result=output)
    return output
