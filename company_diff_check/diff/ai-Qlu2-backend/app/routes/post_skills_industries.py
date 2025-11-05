import traceback
from fastapi import APIRouter
from fastapi.responses import JSONResponse


from app.models.schemas.skills_industries import (
    SkillAndIndustry,
    SkillAndIndustryOutput,
)
from app.utils.search.qsearch.scoring.counts import skills_and_industry_counter
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


@router.post("/skills_industries", response_model=SkillAndIndustryOutput)
async def skills_and_industries(request: SkillAndIndustry):
    try:
        result = await skills_and_industry_counter(dict(request))
    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request.dict(),
            route="/skills_industries",
            service_name="SKILLS & INDUSTRY COUNTER",
        )
        return JSONResponse(status_code=500, content={"message": f"Error {e}"})
    output = SkillAndIndustryOutput(**result)
    return output
