import traceback
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from qutils.slack.notifications import send_slack_notification

from app.models.schemas.dialer.agenda_check import (
    AgendaCheckerRequest,
    AgendaCheckerResponse,
)
from app.utils.dialer.services.agenda_checker.agenda_check import (
    answer_detection_for_agenda,
)

router = APIRouter()


@router.post("/agenda-checker", response_model=AgendaCheckerResponse)
async def agenda_check_(request: AgendaCheckerRequest):
    agenda_input = request.agenda_input
    outbound_list = request.outbound_list
    inbound_list = request.inbound_list
    intent = request.agenda_input.intent

    agenda = agenda_input["data"]
    intent = agenda_input["intent"]

    if intent == "recruitment":
        processing_data = outbound_list
    else:
        processing_data = inbound_list

    if processing_data == []:
        return {"agenda_marked": None}

    try:
        result = await answer_detection_for_agenda(processing_data, agenda)
        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="agenda-checker",
            service_name="DIALER",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
