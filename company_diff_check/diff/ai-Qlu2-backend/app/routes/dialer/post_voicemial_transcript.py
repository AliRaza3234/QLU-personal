import traceback
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.models.schemas.dialer.voicemail_transcript import (
    VoicemailAudioBufferRequest,
    VoicemailTranscripcResponse,
)
from app.utils.dialer.services.voicemail_transcript.voicemail_transcript import (
    transcribe_audio,
)
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/voicemail-trancriber", response_model=VoicemailTranscripcResponse)
async def voicemail_transcriber_buffer(request: VoicemailAudioBufferRequest):
    audio_buffer = request.link
    try:
        transcription = await transcribe_audio(audio_buffer)
        return JSONResponse(status_code=200, content={"transcription": transcription})
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="voicemail-trancriber",
            service_name="DIALER",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
