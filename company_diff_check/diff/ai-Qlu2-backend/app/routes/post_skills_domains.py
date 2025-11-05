import traceback
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.routes.dependancies import get_db_client
from app.utils.people.skills_domains.extract import (
    extract_skills_domains,
    extract_skills_domains_new,
)
from app.models.schemas.skills_domains import SkillsDomainsInput, SkillsDomainsOutput
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/skills_domains", response_model=SkillsDomainsOutput)
async def generate_skills_domains(
    request: SkillsDomainsInput, db_client=Depends(get_db_client)
):

    version = request.version
    if version == "2":
        result = {}
        try:
            result = await extract_skills_domains_new(request, db_client)
        except Exception as e:
            print(e)
            traceback.print_exc()
            error_trace = traceback.format_exc()
            await send_slack_notification(
                traceback=error_trace,
                payload=request.dict(),
                route="/skills_domains",
                service_name="SKILLS & DOMAINS",
            )
            return JSONResponse(status_code=500, content={"message": f"Error {e}"})
        output = SkillsDomainsOutput(output=result)
        return output

    else:
        result = {}
        try:
            result = await extract_skills_domains(request, db_client)
        except Exception as e:
            print(e)
            traceback.print_exc()
            error_trace = traceback.format_exc()
            await send_slack_notification(
                traceback=error_trace,
                payload=request.dict(),
                route="/skills_domains",
                service_name="SKILLS & DOMAINS",
            )
            return JSONResponse(status_code=500, content={"message": f"Error {e}"})
        output = SkillsDomainsOutput(output=result)
        return output
