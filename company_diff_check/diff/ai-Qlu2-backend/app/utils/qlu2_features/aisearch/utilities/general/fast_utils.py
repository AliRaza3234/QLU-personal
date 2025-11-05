import asyncio

from app.utils.qlu2_features.aisearch.utilities.general.general_prompts import (
    WRITING_THE_FIRST_FING_LINE,
)

from app.utils.qlu2_features.aisearch.utilities.llm_functions.llms import (
    grok,
    grok_rewritten,
    claude,
    claude_with_system,
    grok_rewritten_stream,
)
from app.utils.qlu2_features.aisearch.utilities.helper_functions.postgres_functions import (
    insert_into_cache_single_entity_results,
    filters_modification_in_db,
    profile_count_modification_in_db,
    update_value_publicIdentifiers,
    possible_suggestion_filters,
    possible_suggestion_filters_companyTimeline,
)

from app.utils.qlu2_features.aisearch.utilities.general.expansion_variants import (
    call_for_expansion,
    call_for_variants,
)
from app.utils.qlu2_features.aisearch.utilities.helper_functions.misc_functions import (
    last_converter,
)
from app.utils.qlu2_features.aisearch.filters.filters_utils import (
    processing_aisearch_results_suggestions,
)

from app.utils.qlu2_features.aisearch.filters.filters_utils import new_aisearch_results
from app.utils.qlu2_features.aisearch.suggestions.suggestions_utils import (
    suggestions_preparations,
)
from app.utils.qlu2_features.aisearch.suggestions.suggestions_main import suggestions
from app.utils.qlu2_features.aisearch.constants.shared_state import ASYNC_TASKS
from app.utils.qlu2_features.aisearch.utilities.helper_functions.streaming_functions import (
    stream_openai_text,
)
import random

from app.utils.qlu2_features.aisearch.utilities.general.general_prompts import (
    WRITING_THE_FIRST_FING_LINE,
)
from app.utils.qlu2_features.aisearch.utilities.llm_functions.llms import grok_rewritten
from app.utils.qlu2_features.aisearch.utilities.helper_functions.postgres_functions import (
    filters_modification_in_db,
    profile_count_modification_in_db,
)
from app.utils.qlu2_features.aisearch.utilities.general.expansion_variants import (
    call_for_expansion,
    call_for_variants,
)
from app.utils.qlu2_features.aisearch.utilities.helper_functions.misc_functions import (
    last_converter,
)
from app.utils.qlu2_features.aisearch.suggestions.suggestions_main import suggestions
from app.utils.qlu2_features.aisearch.utilities.helper_functions.postgres_functions import (
    update_value_publicIdentifiers,
)
import asyncio


async def writing_the_f_thing(item, already_shown_string, last=False):
    last = False
    formatting_instructions = """
### Formatting Instructions
1.  When writing the question, you need to make sure that the text is in markdown with proper indentation and numbered bullet points.
2.  Preserve the original phrasing of all questions and text. Do not reword, add, or delete anything from the content of the questions.
3.  If it is a single question, and nothing is currently in already_shown_string, then you need to write the question in a single numbered bullet point starting with 1.
4.  If there is already a numbered list in already_shown_string, then you need to write the question in a new numbered bullet point starting with the next number in the sequence.
5.  Numbering and Structure:
    * Use a standard numbered list format (`1.`, `2.`, `3.`, etc.) for all primary questions.
    * If a question in the original text has its own bullet point (`*`, `-`) or number, remove it before placing the question into the new list.
    * Ensure the final list flows in a single ascending sequence of numbered markdown bullet points.
6.  **Sub-Questions:** If a primary question contains a list of sub-questions or items, format them as an indented list directly below it. And make sure that each sub-question is properly indented with 4 spaces and is on a new line in proper markdown format.
7.  **Final Check:** The output must be clean markdown with proper indentation and proper spacing for readability."""
    if not item:
        return ""

    if not last:
        user_prompt = f"<question_to_ask>\n{item}\n</question_to_ask>\n<already_shown_text>\n{already_shown_string}\n</already_shown_text><formatting instructions>{formatting_instructions}</formatting instructions>"
    else:
        user_prompt = f"This is the last question or set of questions. Correctly identify the last question.\n<question_to_ask>\n{item}\n</question_to_ask>\n<already_shown_text>\n{already_shown_string}\n</already_shown_text><formatting instructions>{formatting_instructions}</formatting instructions>"

    messages = [
        {"role": "system", "content": WRITING_THE_FIRST_FING_LINE},
        {"role": "user", "content": user_prompt},
    ]

    rewritten_question = await grok_rewritten(messages)

    return rewritten_question


async def person_mapped_results(
    convId,
    promptId,
    response_id,
    es_client,
    primary_identifier=None,
    reason="update_identifier",
    prompt="",
    profile_count=0,
    result_db=None,
    manual=True,
):
    if reason == "update_identifier":
        async for chunk in update_value_publicIdentifiers(
            convId, promptId, response_id, primary_identifier, es_client
        ):
            yield chunk

    elif reason == "filters":
        if result_db.get("specific_name_search"):
            result_db = {
                "User_Selected_Following_Profile": result_db.get("specific_name_search")
            }
        else:
            result_db = {"AI_Search_Results": result_db}
        success = await filters_modification_in_db(
            convId, promptId, response_id, prompt, result_db
        )
        yield last_converter({"result": success})
    elif reason == "suggestions":
        async for chunk in suggestions(
            convId, promptId, response_id, prompt, False, result_db, manual, es_client
        ):
            yield chunk
    elif reason == "profile_count":
        success = await profile_count_modification_in_db(
            convId, promptId, response_id, prompt, profile_count
        )
        yield last_converter({"result": success})
    elif reason == "variants":
        async for chunk in call_for_variants(
            convId, promptId, response_id, es_client, result_db
        ):
            yield chunk

    elif reason == "expansion":
        async for chunk in call_for_expansion(
            convId, promptId, response_id, es_client, result_db, prompt
        ):
            yield chunk
    return


async def get_full_context(string_second_string, main_query):
    full_context = f"""<Whole_Conversation>\n{string_second_string}<Last_Query>\n{main_query}\n</Last_Query>\n<Whole_Conversation>\n"""

    return full_context


async def _await_next(iterator):
    return await iterator.__anext__()


def _as_task(iterator):
    return asyncio.create_task(_await_next(iterator))


async def no_filter_results_suggestions(prompt, convId, promptId, respId):

    suggestions = [
        "Let me know how I can refine your search to better match what you're looking for.",
        "Need me to adjust the search? Just let me know what you'd like to focus on or change.",
        "Let me know if there's another way you'd like me to refine your search.",
        "Let me know if there's anything else I can help you with.",
    ]
    # return
    sum_of_text = ""
    async for chunk in stream_openai_text(random.choice(suggestions)):
        return_payload = {
            "step": "text_line",
            "text": chunk,
            "response_id": respId + 2,
        }
        yield last_converter(return_payload)
        sum_of_text += chunk

    asyncio.create_task(
        insert_into_cache_single_entity_results(
            convId, promptId, respId + 2, prompt, {"System Follow Up": sum_of_text}
        )
    )
    return


async def handling_grok_replies(
    item,
    last_suggestion,
    convId,
    promptId,
    main_query,
    count_response,
    es_client,
    already_given_suggestions,
    full_context,
    demoBlocked,
):
    if (
        item.get("action", 0)
        and item.get("action", 0) == 1
        and last_suggestion.get("promptId")
    ):
        filters_to_suggest = await possible_suggestion_filters(
            convId, last_suggestion.get("promptId")
        )
        if filters_to_suggest:
            return_payload = {
                "step": "text_line",
                "text": last_suggestion.get("updated_filters_string", ""),
                "response_id": count_response,
            }
            yield last_converter(return_payload)
            count_response += 1

            async for chunk in processing_aisearch_results_suggestions(
                filters_to_suggest,
                count_response,
                last_suggestion.get("suggestion_text", ""),
                convId,
                promptId,
                special_handling=False,
            ):
                yield chunk

            results = [
                {
                    "AI_Search_Results": filters_to_suggest,
                    "clear_prompt": last_suggestion.get("suggestion_text", ""),
                }
            ]
            asyncio.create_task(
                insert_into_cache_single_entity_results(
                    convId, promptId, count_response, main_query, results[0]
                )
            )
            asyncio.create_task(
                suggestions_preparations(
                    main_query,
                    convId,
                    promptId,
                    es_client,
                    already_given_suggestions,
                    demoBlocked=demoBlocked,
                    context=full_context,
                )
            )
            return
    elif not item.get("action"):
        async for chunk in no_filter_results_suggestions(
            main_query, convId, promptId, count_response
        ):
            yield chunk

        return
    elif item.get("action") and item.get("action", 0) == 3:
        sum_of_text = ""
        async for chunk in stream_openai_text(item.get("explanation", "")):
            return_payload = {
                "step": "text_line",
                "text": chunk,
                "response_id": count_response,
            }
            yield last_converter(return_payload)
            sum_of_text += chunk

        results = [{"Explanation": sum_of_text}]
        asyncio.create_task(
            insert_into_cache_single_entity_results(
                convId, promptId, count_response, main_query, results[0]
            )
        )
        return

    yield "Interesting By Arsal and Ali"
    return


async def company_timeline_confirmation(
    company_timeline_task, main_query, convId, promptId, count_response
):
    company_timeline_ambiguity = await company_timeline_task

    if (
        not company_timeline_ambiguity.get("modifications", False)
        and company_timeline_ambiguity.get("selected_timeline", "").lower()
        != "not_selected"
    ):
        filters_to_return = await possible_suggestion_filters_companyTimeline(
            convId, promptId
        )

        if filters_to_return:
            if company_timeline_ambiguity.get("selected_timeline", "").lower() != "and":
                if filters_to_return.get("companies", {}).get(
                    "current"
                ) and filters_to_return.get("companies", {}).get("past"):
                    filters_to_return["companies"]["current"][0] += (
                        ", " + filters_to_return["companies"]["past"][0]
                    )
                    filters_to_return["companies"]["past"] = []
                    filters_to_return["companies"]["timeline"] = (
                        company_timeline_ambiguity.get("selected_timeline")
                    )

            async for chunk in new_aisearch_results(
                main_query,
                filters_to_return,
                count_response,
                convId,
                promptId,
                main_query,
            ):
                yield chunk
            return

    elif (
        company_timeline_ambiguity.get("modifications", False)
        and company_timeline_ambiguity.get("selected_timeline", "").lower()
        != "not_selected"
    ):
        if company_timeline_ambiguity.get("selected_timeline", "").lower() == "current":
            add_to_clear_prompt = f"""<Company_Timeline_Information>Company's Timeline **must be {company_timeline_ambiguity.get("selected_timeline", "")}**, all mentioned industries should be included in current_prompt</Company_Timeline_Information>"""
        elif "or" in company_timeline_ambiguity.get("selected_timeline", "").lower():
            add_to_clear_prompt = f"""<Company_Timeline_Information>Company's Timeline **must be {company_timeline_ambiguity.get("selected_timeline", "")}**, all mentioned industries should be included in either_prompt</Company_Timeline_Information>"""
        elif company_timeline_ambiguity.get("selected_timeline", "").lower() == "past":
            add_to_clear_prompt = f"""<Company_Timeline_Information>Company's Timeline **must be {company_timeline_ambiguity.get("selected_timeline", "")}**, all mentioned industries should be included in past_prompt</Company_Timeline_Information>"""
        elif company_timeline_ambiguity.get("selected_timeline", "").lower() == "and":
            add_to_clear_prompt = f"""<Company_Timeline_Information>Company's Timeline **must be {company_timeline_ambiguity.get("selected_timeline", "")}**, past_prompt and current_prompt both required</Company_Timeline_Information>"""
        yield {"add_to_clear_prompt": add_to_clear_prompt}
        return

    yield ""
    return


async def streaming_the_f_thing(item, already_shown_string, last=False):
    """
    This function now acts as an async generator. It calls the streaming
    model, throttles the incoming tokens to a controlled speed, and yields
    them one by one.
    """
    formatting_instructions = """
### Formatting Instructions
1.  When writing the question, you need to make sure that the text is in markdown with proper indentation and numbered bullet points.
2.  Preserve the original phrasing of all questions and text. Do not reword, add, or delete anything from the content of the questions.
3.  If it is a single question, and nothing is currently in already_shown_string, then you need to write the question in a single numbered bullet point starting with 1.
4.  If there is already a numbered list in already_shown_string, then you need to write the question in a new numbered bullet point starting with the next number in the sequence.
5.  Numbering and Structure:
    * Use a standard numbered list format (`1.`, `2.`, `3.`, etc.) for all primary questions.
    * If a question in the original text has its own bullet point (`*`, `-`) or number, remove it before placing the question into the new list.
    * Ensure the final list flows in a single ascending sequence of numbered markdown bullet points.
6.  **Sub-Questions:** If a primary question contains a list of sub-questions or items, format them as an indented list directly below it. And make sure that each sub-question is properly indented with 4 spaces and is on a new line in proper markdown format.
7.  **Final Check:** The output must be clean markdown with proper indentation and proper spacing for readability."""
    if not item:
        return

    if not last:
        user_prompt = f"<question_to_ask>\n{item}\n</question_to_ask>\n<already_shown_text>\n{already_shown_string}\n</already_shown_text><formatting instructions>{formatting_instructions}</formatting instructions>"
    else:
        user_prompt = f"This is the last question or set of questions. Correctly identify the last question.\n<question_to_ask>\n{item}\n</question_to_ask>\n<already_shown_text>\n{already_shown_string}\n</already_shown_text><formatting instructions>{formatting_instructions}</formatting instructions>"

    messages = [
        {"role": "system", "content": WRITING_THE_FIRST_FING_LINE},
        {"role": "user", "content": user_prompt},
    ]

    # The speed of the "typewriter" effect.
    speed = 0.02

    # Instead of awaiting a full response, we now iterate through the streaming response.
    # We assume grok_rewritten_stream is an async generator you have defined elsewhere.
    async for token in grok_rewritten_stream(messages):
        # Apply the delay BEFORE yielding the token to control the stream speed.
        await asyncio.sleep(speed)
        yield token
