import copy, asyncio, random
import traceback
from app.utils.fastmode.fs_side_functions import get_profile_counts
from app.utils.fastmode.streaming_functions import stream_openai_text

from app.utils.fastmode.postgres_functions import (
    insert_into_cache_single_entity_results,
    fetch_processed_suggestions_preparations_from_db,
)

from app.core.database import postgres_insert

from app.utils.fastmode.helper_functions import last_converter
from app.utils.fastmode.suggestions_utils import (
    expand_management_titles,
    generate_suggestions_agent,
    company_multiple_stream_prompts_agent,
    titles_expansion_suggestions,
    transform_timeline_for_precision,
    precise_suggestions_generation,
    get_industries_with_timelines_and_modifications,
    comp_stream_blocked_flag_agent,
    industry_blocked_flag_agent,
    titles_management_levels_blocked_flag_agent,
    timeline_blocked_flag_agent,
    experience_tenures_education_blocked_flag_agent,
    simple_suggestion_message_agent,
    transform_min_max,
    filters_compstream_new_companies_agent,
    get_atomic_filters,
)

from app.utils.fastmode.prompts import (
    FILTERS_COMPSTREAM_PROMPT,
    FILTERS_INDUSTRY_PROMPT,
    FILTERS_MANAGEMENT_TITLES_PROMPT,
    FILTERS_JOB_TITLES_MANAGEMENT_LEVELS_PROMPT,
    FILTERS_COMPANY_TIMELINE_OR_PROMPT,
    FILTERS_COMPANY_INDUSTRY_TIMELINE_OR_PROMPT,
    FILTERS_EXP_TENURES_PROMPT,
    INDUSTRY_FLAG_DEFINITION,
    COMP_STREAMS_FLAG_DEFINITION,
    MANAGEMENT_TITLES_FLAG_DEFINITION,
    TIMELINE_FLAG_DEFINITION,
    EXPERIENCE_TENURES_EDUCATION_FLAG_DEFINITION,
    P_STRICT_MATCH_SUGGESTION_PROMPT,
    P_CURRENT_TIMELINE_SUGGESTION_PROMPT,
)

from app.utils.fastmode.shared_state import ASYNC_TASKS


def name_search_suggestions():
    suggestions = [
        "Would you like to view a quick summary of ",
        "Want to explore the complete work history of ",
        "Would you like to see the educational background of ",
        "Should we fetch you the contact details of ",
        "Would you like to see the salary trends and pay progression of ",
        "Looking for professionals similar to ",
        "Interested in the core skills and expertise of ",
        "Interested in the industries associated with ",
        "Would you like to review the full professional experience of ",
    ]
    return random.choice(suggestions)


def default_precision_suggestions():
    suggestions = [
        "Let me know how I can refine your search to better match what you're looking for.",
        "Need me to adjust the search? Just let me know what you'd like to focus on or change.",
        "Let me know if there's another way you'd like me to refine your search.",
        "Let me know if there's anything else I can help you with.",
    ]
    return random.choice(suggestions)


def default_strict_match_suggestion():
    suggestions = [
        "Want to make your search more precise? Use exact title matching to narrow down your results."
    ]
    return random.choice(suggestions)


def default_current_timeline_suggestion(modifications):
    company_suggestions = [
        "Would you like to focus only on candidates who currently hold your target roles at your ideal companies?"
    ]
    industry_suggestions = [
        "Would you like to focus only on candidates who currently hold your target roles in your ideal industries?"
    ]
    company_industry_suggestions = [
        "Would you like to focus only on candidates who currently hold your target roles at your ideal companies or industries?"
    ]

    if not modifications:
        return random.choice(company_suggestions)

    if "Company" in modifications and "Industry" not in modifications:
        return random.choice(company_suggestions)
    elif "Company" in modifications and "Industry" in modifications:
        return random.choice(company_industry_suggestions)
    elif "Industry" in modifications and "Company" not in modifications:
        return random.choice(industry_suggestions)
    else:
        return random.choice(company_suggestions)


def no_filter_results_suggestions():
    """
    Returns a random message when a search using filter keywords (job title,
    skills, location, etc.) yields no results, focusing on providing
    clear diagnoses and multiple solutions.
    """
    suggestions = [
        "Let me know how I can refine your search to better match what you're looking for.",
        "Need me to adjust the search? Just let me know what you'd like to focus on or change.",
        "Let me know if there's another way you'd like me to refine your search.",
        "Let me know if there's anything else I can help you with.",
    ]
    return random.choice(suggestions)


def default_company_stream_suggestion():
    suggestions = [
        "Want us to explore multiple company strategies to give you smarter and broader results?"
    ]
    return random.choice(suggestions)


def analyzing_filters_help(filters, count):
    analyzations = []

    if count > 300:
        analyzations.append(
            "The goal for this search would be narrow the results to be less than 300"
        )
    elif count < 100:
        analyzations.append(
            "The goal for this search would be would be to increase the results above 100"
        )
    # elif abs(count - 100) >= abs(count - 300): # closer to 300
    #     analyzations.append("The recall is acceptable. Suggestions goal would, however, be to make the recall closer to a 100")
    elif count > 140:
        analyzations.append(
            "The recall is acceptable but the suggestions goal would be to make the recall closer to a 100 ideally"
        )

    if filters.get("companies") and filters.get("industry"):
        analyzations.append(
            "As company filter and industry filter, both are applied, adding industries would NOT increase recall."
        )

    if filters.get("industry"):
        analyzations.append("No need to add more industries.")

    or_relations_count = 0
    or_relations = "Changing all following filters: "
    for attribute in ["title", "management_level", "companies", "industry"]:
        if filters.get(attribute, {}).get("event", "").lower() != "or":
            if or_relations_count:
                or_relations += ", "

            or_relations += f"{attribute}"
            or_relations_count += 1

    if or_relations_count > 1:
        or_relations += " to OR together would guarantee an increase in recall if and ONLY if ALL these mentioned filters turn to OR; so if increasing results you must suggest turning all these into OR otherwise might not work."
    elif or_relations_count == 1:
        or_relations += " to OR event would increase the results"
    else:
        or_relations = ""

    if count < 100 and or_relations:
        analyzations.append(or_relations)

    analyzations.append(
        "Ensure your suggestion doesn't complete nullify what the user is asking for."
    )

    analyzations_string = ""
    if analyzations:
        analyzations_string = (
            "Key Points you must remember for this set of filters:\n"
            + "\n".join(analyzations)
            + "\n"
        )

    return analyzations_string


async def suggestions(
    convId,
    promptId,
    respId,
    prompt,
    demoBlocked,
    filters,
    manual,
    es_client,  # When Manual is True, we MUST NOT RUN SUGGESTIONS ALI! DO YOU UNDERSTAND
):

    if filters.get("specific_name_search"):
        possible_suggestion = name_search_suggestions()
        possible_suggestion += (
            filters.get("specific_name_search", {}).get("name", "the selected person")
            + "?"
        )

        sum_of_text = ""
        async for chunk in stream_openai_text(possible_suggestion):
            return_payload = {
                "step": "text_line",
                "text": chunk,
                "response_id": respId + 1,
            }
            yield last_converter(return_payload)
            sum_of_text += chunk

        suggestion_text_in_no_temp = [{"Suggestions Agent": sum_of_text}]
        asyncio.create_task(
            insert_into_cache_single_entity_results(
                conversation_id=convId,
                prompt_id=promptId,
                response_id=respId + 1,
                prompt=prompt,
                result=suggestion_text_in_no_temp,
                temp=False,
            )
        )
    # Need to fetch te processed filters from the table single_entity_aisearch_new_temp

    else:
        try:

            if (
                manual
            ):  # When Manual is True, we MUST NOT RUN SUGGESTIONS ALI! DO YOU UNDERSTAND!!!!!!!
                delete_query = f"""
                DELETE FROM single_entity_aisearch_new
                WHERE conversation_id = '{convId}'
                AND prompt_id = {promptId}
                AND response_id > {respId}
            """
                await postgres_insert(delete_query)
                streamed_text = no_filter_results_suggestions()

                async for chunk in stream_openai_text(streamed_text):
                    return_payload = {
                        "step": "text_line",
                        "text": chunk,
                        "response_id": respId + 1,
                    }
                    yield last_converter(return_payload)

                asyncio.create_task(
                    insert_into_cache_single_entity_results(
                        conversation_id=convId,
                        prompt_id=promptId,
                        response_id=respId + 1,
                        prompt=prompt,
                        result=[{"System Follow Up": streamed_text}],
                        temp=False,
                    )
                )

                return

            # Defining some variables
            context = ""  # Context of the conversation
            industry_filters_with_timeline = None  # These are added industry filters, when no industries are currently selected
            modifications_made_in_industry_filters = None  # These are modifications or added industry terms summary for suggestions message generation
            l0_default_filters = copy.deepcopy(filters)
            already_given_suggestions = []
            current_company_short_prompts = []
            past_company_short_prompts = []
            task_company_multiple_stream_prompts_past = None
            task_company_multiple_stream_prompts_current = None
            current_companies_selected = False
            past_companies_selected = False
            companies_selected = False
            current_companies_length = 0
            past_companies_length = 0
            len_of_companies = 0
            titles_expansion_task = None

            # Loading the context, already given suggestions and industry keywords from the database
            processed_filters, already_given_suggestions, source = (
                await fetch_processed_suggestions_preparations_from_db(
                    convId, promptId, demoBlocked
                )
            )

            # Setting processed filters to empty dict if it is None, so it doesn't break on .get() call
            if not processed_filters:
                processed_filters = {}

            if processed_filters.get("original_context", ""):
                context = processed_filters.get("original_context", "")

            # ------------------------------------------------------------------------------------------------
            # Starting Title Expansion Task: (if title suggesstions are not already given)
            # ------------------------------------------------------------------------------------------------
            if filters.get("title", {}) and (
                "titles_management_levels_combo_filters"
                not in already_given_suggestions
            ):
                titles_expansion_task = asyncio.create_task(
                    titles_expansion_suggestions(
                        copy.deepcopy(l0_default_filters.get("title", {})),
                        context,
                    )
                )
            # ------------------------------------------------------------------------------------------------

            # ------------------------------------------------------------------------------------------------
            # Loading the companies selected status and length of selected companies
            # ------------------------------------------------------------------------------------------------
            companies = copy.deepcopy(filters.get("companies", {}))
            companies_event = companies.get("event", "")
            for item in companies["current"]:
                for comp in item.get("pills"):
                    if comp.get("state") == "selected":
                        current_companies_length += 1
                        current_companies_selected = True
            for item in companies["past"]:
                for comp in item.get("pills"):
                    if comp.get("state") == "selected":
                        past_companies_length += 1
                        past_companies_selected = True
            if current_companies_selected or past_companies_selected:
                companies_selected = True
            len_of_companies = current_companies_length + past_companies_length
            # ------------------------------------------------------------------------------------------------

            # ------------------------------------------------------------------------------------------------
            # Loading the industries selected status and length of selected industries
            # ------------------------------------------------------------------------------------------------
            l0_industries = filters.get("industry", {})
            industries_selected = False
            if l0_industries:
                if any(
                    item.get("exclusion") is False
                    for item in l0_industries.get("filter", {}).values()
                ):
                    industries_selected = True
            # ------------------------------------------------------------------------------------------------

            # ------------------------------------------------------------------------------------------------
            # This code is for generating multiple prompts for companies multiple stream if the conditions are met
            # Can be considered a combination for "filters_compstream"
            # ------------------------------------------------------------------------------------------------
            if filters.get("companies", None) and (
                "filters_compstream" not in already_given_suggestions
            ):

                # Sending seperate calls for current companies
                if current_companies_selected:
                    current_company_short_prompts = [
                        item.get("prompt") for item in companies.get("current", [])
                    ]
                    task_company_multiple_stream_prompts_current = asyncio.create_task(
                        company_multiple_stream_prompts_agent(
                            company_description_input=current_company_short_prompts,
                            response_id=-11,
                            convId=convId,
                            promptId=promptId,
                            prompt=prompt,
                        )
                    )

                # Past will only be populated in the event is AND, In case of PAST, past prompts will be coming inside "current" key with Timeline as "PAST"
                if past_companies_selected and companies.get("event", "") == "AND":
                    past_company_short_prompts = [
                        item.get("prompt") for item in companies.get("past", [])
                    ]
                    task_company_multiple_stream_prompts_past = asyncio.create_task(
                        company_multiple_stream_prompts_agent(
                            company_description_input=past_company_short_prompts,
                            response_id=-10,
                            convId=convId,
                            promptId=promptId,
                            prompt=prompt,
                        )
                    )
            # ------------------------------------------------------------------------------------------------

            # ------------------------------------------------------------------------------------------------
            # Deciding Industry Filters along with their timeline from the library function results:
            # ------------------------------------------------------------------------------------------------
            industry_keywords = processed_filters.get("industry_keywords", {})
            industry_filters_with_timeline, modifications_made_in_industry_filters = (
                await get_industries_with_timelines_and_modifications(
                    industry_keywords_input=industry_keywords,
                    l0_filters=l0_default_filters,
                )
            )
            industry_filters_with_timeline = {
                "industry": industry_filters_with_timeline
            }
            # ------------------------------------------------------------------------------------------------

            """
            Following Section is for tweaking and preparing payloads to get the counts of profiles for each filter combination
            """

            # ------------------------------------------------------------------------------------------------
            # Default Filters:
            default_filters = copy.deepcopy(l0_default_filters)
            # ------------------------------------------------------------------------------------------------

            # ------------------------------------------------------------------------------------------------
            # 1. Default Filters Industry Filters:
            industry_combo_filters = None
            if (
                (industry_filters_with_timeline)
                and (companies_selected)
                and (not industries_selected)
                and ("industry_combo_filters" not in already_given_suggestions)
            ):

                industry_combo_filters = copy.deepcopy(l0_default_filters)
                industry_combo_filters.update(industry_filters_with_timeline)
            # ------------------------------------------------------------------------------------------------

            # ------------------------------------------------------------------------------------------------
            # 2. Expanding Only Management Levels:
            management_level_combo_filters = None
            expanded_management_titles = await expand_management_titles(
                l0_default_filters
            )
            if expanded_management_titles and (
                "management_level_combo_filters" not in already_given_suggestions
            ):
                management_level_combo_filters = copy.deepcopy(l0_default_filters)
                management_level_combo_filters.update(
                    {
                        "management_level": expanded_management_titles,
                    }
                )
            # ------------------------------------------------------------------------------------------------

            # ------------------------------------------------------------------------------------------------
            # 3. Expanding Only Titles + Management Levels:
            titles_management_levels_combo_filters = None
            expanded_titles = None
            modifications_made_in_titles = None
            if titles_expansion_task:
                modifications_made_in_titles, expanded_titles = (
                    await titles_expansion_task
                )

            if expanded_titles:
                titles_management_levels_combo_filters = copy.deepcopy(
                    l0_default_filters
                )
                titles_management_levels_combo_filters.update(
                    {
                        "title": expanded_titles,
                    }
                )
            # ------------------------------------------------------------------------------------------------

            # ------------------------------------------------------------------------------------------------
            # 4. Only companies in CURRENT OR PAST
            companies_timeline_OR_combo_filters = None
            if (
                companies_event not in ["OR"]
                and companies_selected
                and (
                    "companies_timeline_OR_combo_filters"
                    not in already_given_suggestions
                )
            ):
                companies_timeline_OR_combo_filters = copy.deepcopy(l0_default_filters)
                companies_timeline_OR_combo_filters["companies"]["event"] = "OR"
            # ------------------------------------------------------------------------------------------------

            # ------------------------------------------------------------------------------------------------
            # 5. Industries in Current or Past (+ if companies not already in OR also add companies in OR)
            industries_companies_timeline_OR_combo_filters = None
            if (
                l0_default_filters.get("industry", {}).get("event", "") not in ["OR"]
                and industries_selected
                and (
                    "industries_companies_timeline_OR_combo_filters"
                    not in already_given_suggestions
                )
            ):
                industries_companies_timeline_OR_combo_filters = copy.deepcopy(
                    l0_default_filters
                )
                industries_companies_timeline_OR_combo_filters["industry"][
                    "event"
                ] = "OR"
                if companies_timeline_OR_combo_filters:
                    industries_companies_timeline_OR_combo_filters["companies"][
                        "event"
                    ] = "OR"
            # ------------------------------------------------------------------------------------------------

            # ------------------------------------------------------------------------------------------------
            # 6. Expanding Experience, Role Tenure and Company Tenure:
            (
                exp_tenures_combo_filters,
                modifications_atomic_list,
                modifications_atomic_string,
            ) = get_atomic_filters(copy.deepcopy(l0_default_filters))
            # ------------------------------------------------------------------------------------------------

            """
            Following are two combinations of Precision Filters Combinations:
            """

            # ------------------------------------------------------------------------------------------------
            # 7. Strict Match on Titles:
            precision_strict_match_combo_filters = None
            if l0_default_filters.get("title", {}):
                if (
                    l0_default_filters.get("title", {}).get("strict_match") is False
                ) and ("strict_match" not in already_given_suggestions):
                    precision_strict_match_combo_filters = copy.deepcopy(
                        l0_default_filters
                    )
                    titles = copy.deepcopy(
                        precision_strict_match_combo_filters.get("title", {})
                    )
                    titles["strict_match"] = True
                    precision_strict_match_combo_filters.update({"title": titles})
            # ------------------------------------------------------------------------------------------------

            # ------------------------------------------------------------------------------------------------
            # 8. Current Timeline:
            precision_current_timeline_combo_filters = None
            precision_current_timeline_modifications = None
            transformed_filters, precision_current_timeline_modifications = (
                await transform_timeline_for_precision(l0_default_filters)
            )
            if transformed_filters and (
                "current_timeline" not in already_given_suggestions
            ):
                precision_current_timeline_combo_filters = copy.deepcopy(
                    transformed_filters
                )

            # ------------------------------------------------------------------------------------------------
            # End of Combinations of Filters
            # ------------------------------------------------------------------------------------------------
            # ------------------------------------------------------------------------------------------------

            # ------------------------------------------------------------------------------------------------
            # Getting the counts of profiles for each filter combination and transforming them to 1000 if they are greater than 1000
            # ------------------------------------------------------------------------------------------------

            (
                default_filters_counts,
                industry_combo_counts,
                management_level_combo_counts,
                titles_management_level_combo_counts,
                companies_timeline_OR_combo_counts,
                industries_companies_timeline_OR_combo_counts,
                exp_tenures_combo_counts,
                precision_strict_match_combo_counts,
                precision_current_timeline_combo_counts,
            ) = await asyncio.gather(
                get_profile_counts(default_filters),
                get_profile_counts(industry_combo_filters),
                get_profile_counts(management_level_combo_filters),
                get_profile_counts(titles_management_levels_combo_filters),
                get_profile_counts(companies_timeline_OR_combo_filters),
                get_profile_counts(industries_companies_timeline_OR_combo_filters),
                get_profile_counts(exp_tenures_combo_filters),
                get_profile_counts(precision_strict_match_combo_filters),
                get_profile_counts(precision_current_timeline_combo_filters),
            )

            default_filters_counts = (
                default_filters_counts.get("count", 0)
                if default_filters_counts.get("count", 0) <= 1000
                else 1000
            )
            industry_combo_counts = (
                industry_combo_counts.get("count", 0)
                if industry_combo_counts.get("count", 0) <= 1000
                else 1000
            )
            management_level_combo_counts = (
                management_level_combo_counts.get("count", 0)
                if management_level_combo_counts.get("count", 0) <= 1000
                else 1000
            )
            titles_management_level_combo_counts = (
                titles_management_level_combo_counts.get("count", 0)
                if titles_management_level_combo_counts.get("count", 0) <= 1000
                else 1000
            )
            companies_timeline_OR_combo_counts = (
                companies_timeline_OR_combo_counts.get("count", 0)
                if companies_timeline_OR_combo_counts.get("count", 0) <= 1000
                else 1000
            )
            industries_companies_timeline_OR_combo_counts = (
                industries_companies_timeline_OR_combo_counts.get("count", 0)
                if industries_companies_timeline_OR_combo_counts.get("count", 0) <= 1000
                else 1000
            )
            exp_tenures_combo_counts = (
                exp_tenures_combo_counts.get("count", 0)
                if exp_tenures_combo_counts.get("count", 0) <= 1000
                else 1000
            )
            precision_strict_match_combo_counts = (
                precision_strict_match_combo_counts.get("count", 0)
                if precision_strict_match_combo_counts.get("count", 0) <= 1000
                else 1000
            )
            precision_current_timeline_combo_counts = (
                precision_current_timeline_combo_counts.get("count", 0)
                if precision_current_timeline_combo_counts.get("count", 0) <= 1000
                else 1000
            )
            # ------------------------------------------------------------------------------------------------
            # End of Counts of Profiles for each filter combination
            # ------------------------------------------------------------------------------------------------
            # ------------------------------------------------------------------------------------------------

            # ------------------------------------------------------------------------------------------------
            # Some preparation code for writing suggestions messages, and some suggestions responses for timeline suggestions
            # ------------------------------------------------------------------------------------------------
            management_levels_modifications = (
                set(expanded_management_titles.get("filter", {}).keys())
                - set(
                    l0_default_filters.get("management_level", {})
                    .get("filter", {})
                    .keys()
                )
                if expanded_management_titles
                else set()
            )

            count = 0
            industry_timeline_suggestion_message = ""
            company_timeline_suggestion_message = ""

            if (
                len_of_companies == 1
                and filters.get("companies", {}).get("event", "") != "OR"
            ):
                company_timeline_suggestion_message = f"Would you like to expand your search to include former employees and anyone with previous experience in this company?"
                industry_timeline_suggestion_message = f"Would you like to expand your search to include former employees and anyone with previous experience in this company or these industries?"
            elif (
                len_of_companies > 1
                and filters.get("companies", {}).get("event", "") != "OR"
            ):
                company_timeline_suggestion_message = f"Would you like to expand your search to include former employees and anyone with previous experience in these companies?"
                industry_timeline_suggestion_message = f"Would you like to expand your search to include former employees and anyone with previous experience in these companies or industries?"
            else:
                company_timeline_suggestion_message = f"Would you like to expand your search to include former employees and anyone with previous experience in these companies?"
                industry_timeline_suggestion_message = f"Would you like to expand your search to include former employees and anyone with previous experience in these industries?"

            # ------------------------------------------------------------------------------------------------

            # ------------------------------------------------------------------------------------------------
            # This dictionary is the main object that has all the information about the statistics of the filters combinations
            # In this dictionary, we have stored the filters with their order of priority
            # ------------------------------------------------------------------------------------------------
            statistics = {
                "default_filters": {
                    "name": "Default Filters",
                    "modifications": [],
                    "count": default_filters_counts,
                    "filters": default_filters,
                    "prompt": "Base Filters for Comparision.",
                },
                "filters_compstream": {
                    "name": "Company Stream Suggestions",
                    "modifications": ["Company"],
                    "count": -1,  # setting -1 here so it does not get used in looped interim keys
                    "filters": (
                        f"{convId}_{promptId}"
                        if ASYNC_TASKS.get(f"{convId}_{promptId}")
                        else None
                    ),
                    "prompt": default_company_stream_suggestion(),
                },
                "industry_combo_filters": {
                    "name": "Default Filters with Added Industry Filters",
                    "modifications": ["Industry"],
                    "count": industry_combo_counts,
                    "filters": industry_combo_filters,
                    "prompt": FILTERS_INDUSTRY_PROMPT.replace(
                        "{{modifications}}", str(modifications_made_in_industry_filters)
                    ),
                },
                "management_level_combo_filters": {
                    "name": "Default Filters with expanded management levels",
                    "modifications": ["Management Level"],
                    "count": management_level_combo_counts,
                    "filters": management_level_combo_filters,
                    "prompt": FILTERS_MANAGEMENT_TITLES_PROMPT.replace(
                        "{{management_levels_modifications}}",
                        str(management_levels_modifications),
                    ),
                },
                "titles_management_levels_combo_filters": {
                    "name": "Default Filters with expanded management levels and expanded titles",
                    "modifications": ["Job Title"],
                    "count": titles_management_level_combo_counts,
                    "filters": titles_management_levels_combo_filters,
                    "prompt": FILTERS_JOB_TITLES_MANAGEMENT_LEVELS_PROMPT.replace(
                        "{{modifications}}", str(modifications_made_in_titles)
                    ),
                },
                "companies_timeline_OR_combo_filters": {
                    "name": "Default Filters without industry keywords, and just changing the timeline of companies to 'Current or Past'",
                    "modifications": ["Company"],
                    "count": companies_timeline_OR_combo_counts,
                    "filters": companies_timeline_OR_combo_filters,
                    "prompt": company_timeline_suggestion_message,
                },
                "industries_companies_timeline_OR_combo_filters": {
                    "name": "Default Filters with changing the timeline of companies and narrow industries to 'Current or Past'",
                    "modifications": (
                        ["Industry", "Company"]
                        if filters.get("companies", {}).get("event", "") != "OR"
                        else ["Industry"]
                    ),
                    "count": industries_companies_timeline_OR_combo_counts,
                    "filters": industries_companies_timeline_OR_combo_filters,
                    "prompt": industry_timeline_suggestion_message,
                },
                "exp_tenures_combo_filters": {
                    "name": "Default Filters with expanded experience, role tenure and company tenure",
                    "modifications": modifications_atomic_list,
                    "count": exp_tenures_combo_counts,
                    "filters": exp_tenures_combo_filters,
                    "prompt": FILTERS_EXP_TENURES_PROMPT.replace(
                        "{{modifications_string}}", modifications_atomic_string
                    ),
                },
            }

            # ------------------------------------------------------------------------------------------------
            # Logging Statistics into DB
            # ------------------------------------------------------------------------------------------------
            asyncio.create_task(
                insert_into_cache_single_entity_results(
                    conversation_id=convId,
                    prompt_id=promptId,
                    response_id=-16,
                    prompt=prompt,
                    result={
                        "Statistics JSON": statistics,
                        "Filters Compstream": (
                            f"{convId}_{promptId}"
                            if ASYNC_TASKS.get(f"{convId}_{promptId}")
                            else None
                        ),
                        "Filters 1 Counts": default_filters_counts,
                        "modifications_made_in_industry_filters": modifications_made_in_industry_filters,
                        "modifications_made_in_titles": modifications_made_in_titles,
                        "already_given_suggestions": already_given_suggestions,
                        "source": source,
                    },
                    temp=True,
                )
            )
            # ------------------------------------------------------------------------------------------------

            # ------------------------------------------------------------------------------------------------
            # Default Variables for Responses and Inserting into DB
            # ------------------------------------------------------------------------------------------------

            stored_filters_in_temp = None
            suggestion_text_in_no_temp = None
            streamed_text = no_filter_results_suggestions()
            baseline_count = default_filters_counts

            interim_suggestions_keys = []
            flags_configs = {}
            flag_tasks = {}
            flag_results = {}
            blocked_filters_flags = []

            # ------------------------------------------------------------------------------------------------
            # Conditional Division for Recall and Precision Suggestions based on the original counts for profiles.
            # ------------------------------------------------------------------------------------------------

            if default_filters_counts <= 100:

                # ------------------------------------------------------------------------------------------------
                # Flags check for whether a particular suggestion should be given or not
                # ------------------------------------------------------------------------------------------------
                flag_configs = {
                    "filters_compstream_current": {
                        "condition": task_company_multiple_stream_prompts_current,
                        "agent_func": comp_stream_blocked_flag_agent,
                        "parameters": current_company_short_prompts,
                    },
                    "filters_compstream_past": {
                        "condition": task_company_multiple_stream_prompts_past,
                        "agent_func": comp_stream_blocked_flag_agent,
                        "parameters": past_company_short_prompts,
                    },
                    "industry_combo_filters_current": {
                        "condition": task_company_multiple_stream_prompts_current,
                        "agent_func": industry_blocked_flag_agent,
                        "parameters": current_company_short_prompts,
                    },
                    "industry_combo_filters_past": {
                        "condition": task_company_multiple_stream_prompts_past,
                        "agent_func": industry_blocked_flag_agent,
                        "parameters": past_company_short_prompts,
                    },
                    "titles_management_levels_combo_filters": {
                        "condition": titles_management_levels_combo_filters,
                        "agent_func": titles_management_levels_blocked_flag_agent,
                        "parameters": context,
                    },
                    "management_level_combo_filters": {
                        "condition": management_level_combo_filters,
                        "agent_func": titles_management_levels_blocked_flag_agent,
                        "parameters": context,
                    },
                    "companies_timeline_OR_combo_filters": {
                        "condition": companies_timeline_OR_combo_filters
                        or industries_companies_timeline_OR_combo_filters,
                        "agent_func": timeline_blocked_flag_agent,
                        "parameters": context,
                    },
                    "exp_tenures_combo_filters": {
                        "condition": exp_tenures_combo_filters,
                        "agent_func": experience_tenures_education_blocked_flag_agent,
                        "parameters": context,
                    },
                }

                # Create tasks for conditions that are met
                flag_tasks = {}
                for flag_name, config in flag_configs.items():
                    if config.get("condition", None):
                        flag_tasks[flag_name] = asyncio.create_task(
                            config["agent_func"](config["parameters"])
                        )
                    else:
                        flag_tasks[flag_name] = "Blocked"

                FLAGS_DEBUGGING_STRING = ""

                # Await all tasks and store results
                flag_results = {}
                for flag_name, task in flag_tasks.items():
                    if task != "Blocked":
                        blocked_flag, blocked_flag_response = await task
                    else:
                        blocked_flag = True
                        blocked_flag_response = "Blocked"
                    FLAGS_DEBUGGING_STRING += (
                        f"-------------------- {flag_name} --------------------\n"
                    )
                    FLAGS_DEBUGGING_STRING += f"{flag_name}\n"
                    FLAGS_DEBUGGING_STRING += f"blocked_flag: {blocked_flag}\n"
                    FLAGS_DEBUGGING_STRING += (
                        f"blocked_flag_response: {blocked_flag_response}\n"
                    )
                    FLAGS_DEBUGGING_STRING += "--------------------------------\n\n"

                    flag_results[flag_name] = {
                        "blocked_flag": blocked_flag,
                        "blocked_flag_response": blocked_flag_response,
                    }

                industry_current_blocked_flag = flag_results.get(
                    "industry_combo_filters_current", {}
                ).get("blocked_flag", True)
                industry_past_blocked_flag = flag_results.get(
                    "industry_combo_filters_past", {}
                ).get("blocked_flag", True)
                filters_compstream_current_blocked_flag = flag_results.get(
                    "filters_compstream_current", {}
                ).get("blocked_flag", True)
                filters_compstream_past_blocked_flag = flag_results.get(
                    "filters_compstream_past", {}
                ).get("blocked_flag", True)
                management_level_blocked_flag = flag_results.get(
                    "management_level_combo_filters", {}
                ).get("blocked_flag", True)
                titles_management_levels_blocked_flag = flag_results.get(
                    "titles_management_levels_combo_filters", {}
                ).get("blocked_flag", True)
                companies_timeline_OR_blocked_flag = flag_results.get(
                    "companies_timeline_OR_combo_filters", {}
                ).get("blocked_flag", True)
                industries_companies_timeline_OR_blocked_flag = flag_results.get(
                    "industries_companies_timeline_OR_combo_filters", {}
                ).get("blocked_flag", True)
                exp_tenures_blocked_flag = flag_results.get(
                    "exp_tenures_combo_filters", {}
                ).get("blocked_flag", True)
                # ------------------------------------------------------------------------------------------------

                # ------------------------------------------------------------------------------------------------
                # Adding the flags to the blocked_filters_flags list
                # ------------------------------------------------------------------------------------------------
                blocked_filters_flags = []
                # ------------------------------------------------------------------------------------------------
                if industry_current_blocked_flag and industry_past_blocked_flag:
                    blocked_filters_flags.append("industry_combo_filters")
                if (
                    filters_compstream_current_blocked_flag
                    and filters_compstream_past_blocked_flag
                ):
                    blocked_filters_flags.append("filters_compstream")
                else:
                    # If multiple stream is not blocked, then we need to append this in ASYNC_TASKS and multiple stream filters can be stored in response_id -15 in Temp DB
                    ASYNC_TASKS[f"{convId}_{promptId}"] = asyncio.create_task(
                        filters_compstream_new_companies_agent(
                            l0_filters=filters,
                            convId=convId,
                            promptId=promptId,
                            prompt=prompt,
                            current_task=task_company_multiple_stream_prompts_current,
                            current_blocked=filters_compstream_current_blocked_flag,
                            past_task=task_company_multiple_stream_prompts_past,
                            past_blocked=filters_compstream_past_blocked_flag,
                        )
                    )

                if management_level_blocked_flag:
                    blocked_filters_flags.append("management_level_combo_filters")
                if titles_management_levels_blocked_flag:
                    blocked_filters_flags.append(
                        "titles_management_levels_combo_filters"
                    )
                if companies_timeline_OR_blocked_flag:
                    blocked_filters_flags.append("companies_timeline_OR_combo_filters")
                if industries_companies_timeline_OR_blocked_flag:
                    blocked_filters_flags.append(
                        "industries_companies_timeline_OR_combo_filters"
                    )
                if exp_tenures_blocked_flag:
                    blocked_filters_flags.append("exp_tenures_combo_filters")
                # ------------------------------------------------------------------------------------------------

                # ------------------------------------------------------------------------------------------------
                # Storing conditions for debugging purposes
                # ------------------------------------------------------------------------------------------------

                conditions_debug_multiple_stream = {
                    "async_task_exists": bool(ASYNC_TASKS.get(f"{convId}_{promptId}")),
                    "default_count_above_20": default_filters_counts > 20,
                    "no_industries_selected": not industries_selected,
                    "compstream_not_in_suggestions": "filters_compstream"
                    not in already_given_suggestions,
                    "compstream_not_blocked": "filters_compstream"
                    not in blocked_filters_flags,
                    "companies_exist": bool(filters.get("companies", None)),
                }

                conditions_dict = {
                    "filters_compstream": (
                        "True" if ASYNC_TASKS.get(f"{convId}_{promptId}") else "False"
                    ),
                    "industry_combo_filters": (
                        "True" if industry_combo_filters else "False"
                    ),
                    "titles_management_levels_combo_filters": (
                        "True" if titles_management_levels_combo_filters else "False"
                    ),
                    "management_level_combo_filters": (
                        "True" if management_level_combo_filters else "False"
                    ),
                    "companies_timeline_OR_combo_filters": (
                        "True"
                        if companies_timeline_OR_combo_filters
                        or industries_companies_timeline_OR_combo_filters
                        else "False"
                    ),
                    "exp_tenures_combo_filters": (
                        "True" if exp_tenures_combo_filters else "False"
                    ),
                    "precision_strict_match_combo_filters": (
                        "True" if precision_strict_match_combo_filters else "False"
                    ),
                    "precision_current_timeline_combo_filters": (
                        "True" if precision_current_timeline_combo_filters else "False"
                    ),
                }

                asyncio.create_task(
                    insert_into_cache_single_entity_results(
                        conversation_id=convId,
                        prompt_id=promptId,
                        response_id=-12,
                        prompt=prompt,
                        result={
                            "flag_results": flag_results,
                            "blocked_filters_flags": blocked_filters_flags,
                            "conditions_dict": conditions_dict,
                            "flags_debugging_string": FLAGS_DEBUGGING_STRING,
                            "multiple_stream_condition": conditions_debug_multiple_stream,
                        },
                        temp=True,
                    )
                )
                # ------------------------------------------------------------------------------------------------

                # ------------------------------------------------------------------------------------------------
                # Interim Suggestions Keys, is a list in which we store those suggestions that resulted in increased profile count than the original baseline count.
                # Since, we also know which suggestions are blocked or not, and the priority of the suggestions is already stored in the statistics dictionary,
                # we can easily add the keys to the interim_suggestions_keys list and the key at the 0th index will be the most prioritized suggestion.
                # Adding the keys to the interim_suggestions_keys list
                # ------------------------------------------------------------------------------------------------
                for key, value in statistics.items():
                    if value.get("count") != -1:
                        count = value.get("count")
                        if count > baseline_count:
                            interim_suggestions_keys.append(key)

                if (
                    default_filters_counts > 20
                    and not industries_selected
                    and "filters_compstream" not in already_given_suggestions
                    and "filters_compstream" not in blocked_filters_flags
                    and bool(filters.get("companies", None))
                ):

                    # ------------------------------------------------------------------------------------------------
                    # If profile count is greater than 20, then we should not be giving industry suggestions, rather we should be giving company stream suggestions.
                    # Therefore, Remove industry_combo_filters from interim_suggestions_keys if present because count > 20 so no need to suggest industry, rather comp_stream
                    # ------------------------------------------------------------------------------------------------
                    interim_suggestions_keys = [
                        key
                        for key in interim_suggestions_keys
                        if key not in ["industry_combo_filters"]
                    ]
                    if bool(
                        ASYNC_TASKS.get(f"{convId}_{promptId}")
                    ):  # double checking if the task exists or not
                        # Add company stream suggestions to the beginning of interim_suggestions_keys,
                        interim_suggestions_keys.insert(0, "filters_compstream")

                # Removing already given suggestions from interim_suggestions_keys
                interim_suggestions_keys = [
                    key
                    for key in interim_suggestions_keys
                    if key not in already_given_suggestions
                ]

                # Removing blocked filters from interim_suggestions_keys
                interim_suggestions_keys = [
                    key
                    for key in interim_suggestions_keys
                    if key not in blocked_filters_flags
                ]

                # ------------------------------------------------------------------------------------------------
                # Selecting the most prioritized suggestion and it's prompt from the interim_suggestions_keys list after getting rid of already given suggestions and blocked suggestions
                # ------------------------------------------------------------------------------------------------

                suggestion_filters_key = (
                    interim_suggestions_keys[0] if interim_suggestions_keys else None
                )

                instruction_prompt = statistics.get(
                    str(suggestion_filters_key), {}
                ).get("prompt")
                suggestions_text = ""
                if suggestion_filters_key:
                    # ------------------------------------------------------------------------------------------------
                    # If the suggestion has hardcoded replies that do not require LLM, we just directly use the stored hardcoded reply.
                    # ------------------------------------------------------------------------------------------------
                    if suggestion_filters_key in [
                        "filters_compstream",
                        "companies_timeline_OR_combo_filters",
                        "industries_companies_timeline_OR_combo_filters",
                    ]:
                        suggestions_text = instruction_prompt
                    else:
                        # ------------------------------------------------------------------------------------------------
                        # If the suggestion requires LLM transformation, we use the simple_suggestion_message_agent to get the suggestion text. e.g., for writing industry keywords, management levels, experience tenures, etc.
                        # ------------------------------------------------------------------------------------------------
                        suggestions_text = await simple_suggestion_message_agent(
                            context, instruction_prompt
                        )

                # Deciding text for streaming and storing in DB
                selected_filters = None
                stored_filters_in_temp = None
                streamed_text = no_filter_results_suggestions()
                suggestion_text_in_no_temp = [{"System Follow Up": streamed_text}]

                if suggestion_filters_key:
                    selected_filters = statistics.get(suggestion_filters_key).get(
                        "filters"
                    )

                    # Special Handling of Storing Replies for Company Stream Suggestions
                    if suggestion_filters_key == "filters_compstream":
                        streamed_text = default_company_stream_suggestion()
                        suggestion_text_in_no_temp = [
                            {
                                "Suggestions Agent": streamed_text,
                                "approach": suggestion_filters_key,
                                "modifications": statistics.get(
                                    suggestion_filters_key
                                ).get("modifications"),
                            }
                        ]
                        stored_filters_in_temp = {
                            "filters_number": "filters_compstream",
                            "await_task_key": (
                                f"{convId}_{promptId}"
                                if ASYNC_TASKS.get(f"{convId}_{promptId}")
                                else None
                            ),
                            "selected_filters": {},
                        }
                    # All other suggestions cases, need to have the following structure:
                    else:
                        streamed_text = suggestions_text.strip()
                        suggestion_text_in_no_temp = [
                            {
                                "Suggestions Agent": streamed_text,
                                "approach": suggestion_filters_key,
                                "modifications": statistics.get(
                                    suggestion_filters_key
                                ).get("modifications"),
                            }
                        ]
                        stored_filters_in_temp = {
                            "filters_number": suggestion_filters_key,
                            "selected_filters": selected_filters,
                        }

                # Storing the Recall Information in the cache for debugging purposes with response id -17
                asyncio.create_task(
                    insert_into_cache_single_entity_results(
                        conversation_id=convId,
                        prompt_id=promptId,
                        response_id=-17,
                        prompt=prompt,
                        result={
                            "Selected Filters": selected_filters,
                            "Stored Filters in Temp": stored_filters_in_temp,
                            "Streamed Text": streamed_text,
                            "Suggestion Text in No Temp": suggestion_text_in_no_temp,
                            "interim_suggestions_keys": interim_suggestions_keys,
                        },
                        temp=True,
                    )
                )

            elif default_filters_counts > 200:

                # ------------------------------------------------------------------------------------------------
                # Precision Suggestions
                # ------------------------------------------------------------------------------------------------

                precision_statistics = {
                    "strict_match": {
                        "name": "Default Filters with strict match on titles",
                        "modifications": ["Job Title"],
                        "count": precision_strict_match_combo_counts,
                        "filters": precision_strict_match_combo_filters,
                        "prompt": default_strict_match_suggestion(),
                    },
                    "current_timeline": {
                        "name": "Default Filters Current Timeline",
                        "modifications": precision_current_timeline_modifications,
                        "count": precision_current_timeline_combo_counts,
                        "filters": precision_current_timeline_combo_filters,
                        "prompt": default_current_timeline_suggestion(
                            precision_current_timeline_modifications
                        ),
                    },
                }

                # ------------------------------------------------------------------------------------------------
                # Selecting the most prioritized suggestion from the precision_statistics dictionary
                # check the closest to hundred count and less than default_filters_counts and greater than 100
                # ------------------------------------------------------------------------------------------------
                strict_match_count = 10000
                selected_suggestion = "default"
                selected_filters = None

                if precision_strict_match_combo_counts:
                    if (
                        precision_strict_match_combo_counts < default_filters_counts
                        and precision_strict_match_combo_counts >= 80
                    ):
                        strict_match_count = precision_strict_match_combo_counts
                        if "strict_match" not in already_given_suggestions:
                            selected_suggestion = "strict_match"
                            selected_filters = precision_strict_match_combo_filters
                if precision_current_timeline_combo_counts:
                    if (
                        precision_current_timeline_combo_counts < default_filters_counts
                        and precision_current_timeline_combo_counts >= 80
                        and precision_current_timeline_combo_counts < strict_match_count
                    ):
                        if "current_timeline" not in already_given_suggestions:
                            selected_suggestion = "current_timeline"
                            selected_filters = precision_current_timeline_combo_filters

                # ------------------------------------------------------------------------------------------------

                # ------------------------------------------------------------------------------------------------
                # Deciding the text for streaming and storing in DB
                # ------------------------------------------------------------------------------------------------
                if selected_suggestion == "strict_match":
                    streamed_text = default_strict_match_suggestion()
                    suggestion_text_in_no_temp = [
                        {
                            "Suggestions Agent": streamed_text,
                            "approach": "strict_match",
                            "modifications": ["Job Title"],
                        }
                    ]
                    stored_filters_in_temp = {
                        "filters_number": "strict_match",
                        "selected_filters": selected_filters,
                    }
                elif selected_suggestion == "current_timeline":
                    streamed_text = default_current_timeline_suggestion(
                        precision_current_timeline_modifications
                    )
                    suggestion_text_in_no_temp = [
                        {
                            "Suggestions Agent": streamed_text,
                            "approach": "current_timeline",
                            "modifications": precision_current_timeline_modifications,
                        }
                    ]
                    stored_filters_in_temp = {
                        "filters_number": "current_timeline",
                        "selected_filters": selected_filters,
                    }
                else:
                    streamed_text = default_precision_suggestions()
                    suggestion_text_in_no_temp = [{"System Follow Up": streamed_text}]
                    stored_filters_in_temp = None
                # ------------------------------------------------------------------------------------------------

                # Storing the precision statistics in the cache for debugging purposes with response id -12
                asyncio.create_task(
                    insert_into_cache_single_entity_results(
                        conversation_id=convId,
                        prompt_id=promptId,
                        response_id=-13,
                        prompt=prompt,
                        result={
                            "Precision Statistics": precision_statistics,
                            "Selected Suggestion": selected_suggestion,
                            "Selected Filters": selected_filters,
                            "Streamed Text": streamed_text,
                            "Suggestion Text in No Temp": suggestion_text_in_no_temp,
                        },
                        temp=True,
                    )
                )

            else:
                # ------------------------------------------------------------------------------------------------
                # Setting Default Value
                # ------------------------------------------------------------------------------------------------
                stored_filters_in_temp = None
                suggestion_text_in_no_temp = [{"System Follow Up": streamed_text}]

            # ------------------------------------------------------------------------------------------------
            # Storing the Replies and Temp Values in the DB, and yielding the streamed text
            # ------------------------------------------------------------------------------------------------
            asyncio.create_task(
                insert_into_cache_single_entity_results(
                    conversation_id=convId,
                    prompt_id=promptId,
                    response_id=-2,
                    prompt=prompt,
                    result=stored_filters_in_temp,
                    temp=True,
                )
            )

            asyncio.create_task(
                insert_into_cache_single_entity_results(
                    conversation_id=convId,
                    prompt_id=promptId,
                    response_id=respId + 1,
                    prompt=prompt,
                    result=suggestion_text_in_no_temp,
                    temp=False,
                )
            )
            sum_of_text = ""
            async for chunk in stream_openai_text(streamed_text):
                return_payload = {
                    "step": "text_line",
                    "text": chunk,
                    "response_id": respId + 1,
                }
                yield last_converter(return_payload)
                sum_of_text += chunk

            # ------------------------------------------------------------------------------------------------
            # End of Streaming the Text
            # ------------------------------------------------------------------------------------------------

            return
        except Exception as e:
            # Capture the full traceback as a string
            tb_str = traceback.format_exc()

            streamed_text = no_filter_results_suggestions()
            # Store the error logs in the db
            asyncio.create_task(
                insert_into_cache_single_entity_results(
                    conversation_id=convId,
                    prompt_id=promptId,
                    response_id=-420,
                    prompt=prompt,
                    result={
                        "error_message": str(e),
                        "traceback": tb_str,
                    },
                    temp=True,
                )
            )
            asyncio.create_task(
                insert_into_cache_single_entity_results(
                    conversation_id=convId,
                    prompt_id=promptId,
                    response_id=respId + 1,
                    prompt=prompt,
                    result=[{"System Follow Up": streamed_text}],
                    temp=False,
                )
            )
            sum_of_text = ""
            async for chunk in stream_openai_text(streamed_text):
                return_payload = {
                    "step": "text_line",
                    "text": chunk,
                    "response_id": respId + 1,
                }
                yield last_converter(return_payload)
                sum_of_text += chunk

            # Sending the error message to the frontend network to know suggestion was failed
            return_payload = {
                "step": "suggestions_failed",
                "text": "Suggestions Failed",
                "response_id": -420,
            }
            yield last_converter(return_payload)

            return
