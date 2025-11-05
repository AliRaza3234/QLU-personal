import asyncio

from app.utils.qlu2_features.aisearch.suggestions.suggestions_prompts import (
    SUGGESTION_ACCEPTANCE_PROMPT,
    Multiple_Streams_Suggestion,
    Industry_Explanation,
    Job_Title_Explanation,
    Management_Level_Explanation,
    Company_Timeline_OR_Explanation,
    Industry_Timeline_OR_Explanation,
    Atomic_Filters_Experience_Explanation,
    Atomic_Filters_Company_Tenure_Explanation,
    Atomic_Filters_Role_Tenure_Explanation,
    Strict_Match_Explanation,
    Current_Timeline_Company_Explanation,
    Current_Timeline_Industry_Explanation,
)

from app.utils.qlu2_features.aisearch.utilities.llm_functions.llms import grok

from app.utils.qlu2_features.aisearch.utilities.general.fast_utils import (
    handling_grok_replies,
)
from app.utils.qlu2_features.aisearch.constants.shared_state import ASYNC_TASKS
from app.utils.qlu2_features.aisearch.constants.aisearch_constants import PREFIX_STATE

modification_keys = {
    "filters_compstream": Multiple_Streams_Suggestion,
    "industry_combo_filters": Industry_Explanation,
    "management_level_combo_filters": Management_Level_Explanation,
    "titles_management_levels_combo_filters": Job_Title_Explanation,
    "companies_timeline_OR_combo_filters": Company_Timeline_OR_Explanation,
    "strict_match": Strict_Match_Explanation,
}


def build_suggestion_explanation(approach, modified_filters, modification_keys):
    explanation = ""
    if approach in modification_keys:
        explanation = modification_keys.get(approach)
        if approach == "exp_tenures_combo_filters":
            explanation = explanation.replace("[]", modified_filters)
    else:
        if approach == "current_timeline":
            if "Company" in modified_filters:
                explanation = f"{Company_Timeline_OR_Explanation}"
            if "Industry" in modified_filters:
                explanation += f"{Industry_Timeline_OR_Explanation}"
        elif approach == "industries_companies_timeline_OR_combo_filters":
            if "Company" in modified_filters:
                explanation = f"{Current_Timeline_Company_Explanation}"
            if "Industry" in modified_filters:
                explanation += f"{Current_Timeline_Industry_Explanation}"
        elif approach == "exp_tenures_combo_filters":
            if "Experience" in modified_filters:
                explanation = Atomic_Filters_Experience_Explanation
            if "Company Tenure" in modified_filters:
                explanation += Atomic_Filters_Role_Tenure_Explanation
            if "Role Tenure" in modified_filters:
                explanation += Atomic_Filters_Company_Tenure_Explanation

    return explanation


async def handle_suggestions_acceptance(
    convId,
    promptId,
    main_query,
    last_suggestion,
    already_suggested_list,
    full_context,
    count_response,
    es_client,
    demoBlocked,
):

    if last_suggestion:
        approach = already_suggested_list[-1]
        modified_filters = last_suggestion.get("modified_filters", [])
        explanation = build_suggestion_explanation(
            approach, modified_filters, modification_keys
        )

        suggestion_acceptance = [
            {"role": "system", "content": f"{SUGGESTION_ACCEPTANCE_PROMPT}"},
            {
                "role": "user",
                "content": f"""Context: {full_context}\nLast_Suggestion: {last_suggestion.get("suggestion", "")}\nSuggestion's explanation:{explanation}""",
            },
        ]

        suggestion_acceptance_task = asyncio.create_task(grok(suggestion_acceptance))
        item_suggested = await suggestion_acceptance_task
        if isinstance(item_suggested, dict) and "action" in item_suggested:
            async for chunk in handling_grok_replies(
                item_suggested,
                last_suggestion,
                convId,
                promptId,
                main_query,
                count_response,
                es_client,
                already_suggested_list,
                full_context,
                demoBlocked,
            ):
                if chunk != "Interesting By Arsal and Ali":
                    yield chunk

            if chunk != "Interesting By Arsal and Ali":
                ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"][
                    "suggestions_acceptance"
                ] = True
            else:
                ASYNC_TASKS[f"{PREFIX_STATE}_{convId}_{promptId}"][
                    "suggestions_acceptance"
                ] = False
    return
