import traceback
from fastapi import APIRouter, BackgroundTasks, HTTPException
from app.models.schemas.suggest_terms import SuggestTermsInput, SuggestTermsOutput
from app.core.database import cache_data, get_cached_data
from app.utils.search.qsearch.suggestions.pills import suggest_terms
from qutils.slack.notifications import send_slack_notification

router = APIRouter()


def remove_words_with_multiple_spaces(strings):
    updated_strings = []
    for string in strings:
        if " ".count(string) <= 1:
            updated_strings.append(string)
    return updated_strings


@router.post("/suggest_terms", response_model=SuggestTermsOutput)
async def suggest_terms_api(
    request: SuggestTermsInput, background_task: BackgroundTasks
) -> list[str]:
    """
    # Suggest Terms
    Given an entity of a specific type, suggest similar entities
    ## Args:
    * **entity**: Entity name e.g. Vp of Finance, VR Headsets etc.
    * **entity_type**: Entity Type, e.g. titles, industries etc. - Supported values: [titles, industries, companies, skills]
    """
    try:
        cache_key = f"v2-suggest-terms~{request.entity_type}~{request.entity}".lower()
        if request.entity_type == "industries":
            cached_suggested_term_list = []
        else:
            cached_suggested_term_list = await get_cached_data(
                cache_key, "general_purpose_cache"
            )

        if cached_suggested_term_list:
            return SuggestTermsOutput(
                suggested_terms=cached_suggested_term_list["gpt-4o-mini"]
            )

        suggested_term_list = await suggest_terms(request.entity, request.entity_type)
        suggested_term_list = [i.replace("*", "") for i in suggested_term_list]
        if request.entity == "skills" or "industries":
            suggested_term_list = remove_words_with_multiple_spaces(suggested_term_list)

        background_task.add_task(
            cache_data,
            cache_key,
            {"gpt-4o-mini": suggested_term_list},
            "general_purpose_cache",
        )
        output = SuggestTermsOutput(suggested_terms=suggested_term_list)
        return output

    except Exception as e:
        print(e)
        traceback.print_exc()
        error_trace = traceback.format_exc()
        await send_slack_notification(
            traceback=error_trace,
            payload=request,
            route="suggest_terms",
            service_name="SUGGESTIVE PILLS",
        )
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while processing the request. Traceback: {error_trace}",
        )
