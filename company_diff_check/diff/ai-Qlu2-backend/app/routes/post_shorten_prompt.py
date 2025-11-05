import traceback
from typing import Union
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from qutils.slack.notifications import send_slack_notification

from app.utils.search.aisearch.company.generation.shorten import (
    dual_shorten_prompt,
)
from app.utils.search.aisearch.company.generation.misc import (
    generate_more_prompt_refine,
)
from app.models.schemas.shorten_prompt import (
    ShortenPromptInput,
    ShortenPromptOutput,
    DualShortenPromptOutput,
    ClusterCompaniesInput,
    ClusterCompaniesOutput,
)

router = APIRouter()


@router.post(
    "/shorten_prompt",
    response_model=Union[ShortenPromptOutput, DualShortenPromptOutput],
)
async def shorten_prompt(request: ShortenPromptInput):
    prompt = request.prompt
    agent = request.agent
    response = {}
    if agent == "dual":
        try:
            response = await dual_shorten_prompt(prompt)
        except Exception as e:
            error_trace = traceback.format_exc()
            await send_slack_notification(
                traceback=error_trace,
                payload=request,
                route="shorten_prompt",
                service_name="COMPANY GENERATION",
            )
            return JSONResponse(status_code=500, content={"message": f"Error {e}"})
        output = DualShortenPromptOutput(**response)
        if all(value is None for value in response.values()):
            return JSONResponse(status_code=200, content=None)
    else:
        pass

    return output


@router.post("/generate_more_prompt", response_model=ClusterCompaniesOutput)
async def generate_more_prompt(request: ClusterCompaniesInput):
    prompt = request.prompt
    companies = request.companies
    try:
        response = await generate_more_prompt_refine(prompt, companies)
    except Exception as e:
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="generate_more_prompt",
            service_name="COMPANY GENERATION",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
    output = ClusterCompaniesOutput(refined_prompt=response)
    return output
