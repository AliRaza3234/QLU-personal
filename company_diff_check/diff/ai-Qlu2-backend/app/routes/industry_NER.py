import traceback
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.models.schemas.industry_NER import IndustryNERInput
from app.utils.qlu2_features.aisearch.question_answers.qa_agents import (
    industry_detection_from_input_stream_agent,
)

router = APIRouter()


@router.post("/aisearch/NER")
async def NER_Service(request: IndustryNERInput):
    convId = request.convId
    promptId = request.promptId
    text = request.text
    demoBlocked = request.demoBlocked

    try:
        response = await industry_detection_from_input_stream_agent(
            convId, promptId, text, demoBlocked
        )
        return JSONResponse({"result": response})
    except Exception as e:
        traceback.print_exc()
        error_trace = traceback.format_exc()
        return JSONResponse(content={"result": "Error"}, status_code=500)
