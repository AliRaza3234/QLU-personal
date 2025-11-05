import traceback
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from qutils.slack.notifications import send_slack_notification

from app.models.schemas.dialer.set_agenda import (
    AgendaSetterRequest,
    AgendaSetterResponse,
)
from app.utils.dialer.services.set_agenda.set_agenda import agenda_formatting


router = APIRouter()


@router.post("/set-agendas", response_model=AgendaSetterResponse)
async def set_agendas(request: AgendaSetterRequest):
    text = request.text
    text = request.strip()
    try:
        formatted_agenda = await agenda_formatting(text)
        return formatted_agenda
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="set-agendas",
            service_name="DIALER",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
