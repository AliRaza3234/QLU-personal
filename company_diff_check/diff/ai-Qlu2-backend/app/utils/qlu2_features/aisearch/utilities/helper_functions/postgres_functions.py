import asyncio, json
from app.core.database import postgres_fetch, postgres_insert

from sqlalchemy.sql import text
from app.routes.dependancies import get_sqlalchemy_session_ai
from sqlalchemy import bindparam
from sqlalchemy.dialects.postgresql import JSONB
from app.utils.qlu2_features.aisearch.constants.shared_state import ASYNC_TASKS

from app.utils.qlu2_features.aisearch.utilities.general.summary import summary_text
from app.utils.qlu2_features.aisearch.utilities.helper_functions.misc_functions import (
    transform_context,
    last_converter,
)
from app.utils.qlu2_features.aisearch.utilities.helper_functions.streaming_functions import (
    stream_openai_text,
)

import traceback


async def postgres_insert_custom(
    convId, promptId, response_id, prompt, result_data
) -> bool:

    stmt = text(
        """
        INSERT INTO single_entity_aisearch_new (conversation_id, prompt_id, response_id, prompt, result)
        VALUES (:conversation_id, :prompt_id, :response_id, :prompt, :result)
    """
    )

    async with get_sqlalchemy_session_ai() as session:
        try:
            await session.execute(
                stmt,
                {
                    "conversation_id": convId,
                    "prompt_id": promptId,
                    "response_id": response_id,
                    "prompt": prompt,
                    "result": json.dumps(result_data),  # Use proper json.dumps here
                },
            )
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            print(f"An error occurred: {e}")
            return False


async def postgres_insert_custom_temp(
    convId, promptId, response_id, prompt, result_data
) -> bool:

    stmt = text(
        """
        INSERT INTO single_entity_aisearch_new_temp (conversation_id, prompt_id, response_id, prompt, result)
        VALUES (:conversation_id, :prompt_id, :response_id, :prompt, :result)
    """
    )

    async with get_sqlalchemy_session_ai() as session:
        try:
            await session.execute(
                stmt,
                {
                    "conversation_id": convId,
                    "prompt_id": promptId,
                    "response_id": response_id,
                    "prompt": prompt,
                    "result": json.dumps(result_data),  # Use proper json.dumps here
                },
            )
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            print(f"An error occurred: {e}")
            return False


async def insert_into_cache_single_entity_results(
    conversation_id, prompt_id, response_id, prompt, result, temp=False
):

    if not temp:
        success = await postgres_insert_custom(
            conversation_id, prompt_id, response_id, prompt, result
        )
    else:
        success = await postgres_insert_custom_temp(
            conversation_id, prompt_id, response_id, prompt, result
        )


async def postgres_fetch_custom(query: str):
    async with get_sqlalchemy_session_ai() as session:
        try:
            result = await session.execute(text(query))
            return result.fetchall()
        except Exception as e:
            print(f"Error in fetching: {e}, Exception type: {type(e)}")
            print(traceback.format_exc())
        return None


async def postgres_insert_custom_for_filters(query: str, params=None) -> bool:
    async with get_sqlalchemy_session_ai() as session:
        try:
            if params is None:
                await session.execute(query)
            else:
                await session.execute(query, params)
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            print(f"An error occurred: {e}")
            return False


async def fetch_from_cache_single_entity_results(
    conversation_id, promptId, demoBlocked
):
    # result_json = json.dumps(result)

    query = f"""
        select prompt, result, prompt_id from single_entity_aisearch_new where conversation_id = '{conversation_id}' and prompt_id < '{promptId}' ORDER BY prompt_id, response_id;
    """

    complete_results = await postgres_fetch_custom(query)

    if not complete_results:
        return "", False, False, False, {}, False, [], False, []

    # result = [item for item in result]
    complete_string = ""
    # aisearch_used_till_now = False
    aisearches = {}
    index = -1
    temp_prompt_id = 0
    all_string_content = []

    industry_flag = False
    industry_flag_ = False
    last_aisearch = False
    last_suggestion = {}
    and_question_asked = False
    prompt_id_max = 0
    for i in range(len(complete_results) - 1, -1, -1):
        item = complete_results[i]
        result = item[1]
        prompt_id_temp = item[2]
        if prompt_id_temp > prompt_id_max:
            prompt_id_max = prompt_id_temp

        if (
            isinstance(result, dict)
            and result.get("AI_Search_Results", "")
            and isinstance(result.get("AI_Search_Results", ""), dict)
        ):
            if result.get("AI_Search_Results", {}).get("industry"):
                industry_flag_ = True

            if prompt_id_temp == prompt_id_max:
                last_aisearch = True
            break

        if isinstance(result, dict) and result.get("and_question", False):
            if prompt_id_temp == prompt_id_max:
                and_question_asked = result.pop("and_question", True)

    already_suggested_list = []
    max_suggestion_index = -1
    if isinstance(result, list) and len(result) == 1 and isinstance(result[0], dict):
        pass

    clarification = False
    questions = []
    for index_number, item in enumerate(complete_results):
        prompt = item[0]
        result = item[1]
        prompt_id = item[2]

        if temp_prompt_id != prompt_id:
            if index >= 0:
                all_string_content.append(f"</Result-{index}>\n")

            index = index + 1
            temp_prompt_id = prompt_id
            all_string_content.append(
                f"<User_Query-{index}>\n{prompt}\n</User_Query-{index}>\n<Result-{index}>\n"
            )

        if isinstance(result, dict) and result.get("AI_Search_Results", ""):
            last_suggestion = {}
            questions = []
            if isinstance(result.get("AI_Search_Results", ""), dict):
                aisearches[index] = {
                    "prompt": result.get("clear_prompt", ""),
                    "result": result["AI_Search_Results"],
                }
                result.pop("clear_prompt", None)
                result = transform_context(
                    result["AI_Search_Results"], industry_flag, demoBlocked
                )
            else:
                result = "Done Nothing"

        if (
            isinstance(result, dict)
            and result.get("System Follow Up", "")
            and result.get("questions", [])
        ):
            questions = result.pop("questions", [])

        if (
            len(result) == 1
            and isinstance(result, list)
            and isinstance(result[0], dict)
            and result[0].get("Suggestions Agent", "")
        ):
            already_suggested_list.append(result[0].pop("approach", None))
            result = result[0]

            last_suggestion["suggestion_text"] = (
                f"""Implement the following suggestion: "{result.get("Suggestions Agent", "")}" """
            )
            last_suggestion["suggestion"] = result.get("Suggestions Agent", "")

            last_suggestion["modified_filters"] = result.pop("modifications", [])

            if len(last_suggestion["modified_filters"]) > 1:
                last_suggestion["updated_filters_string"] = (
                    "Updated Filters: "
                    + ", ".join(last_suggestion["modified_filters"])
                    + "\n"
                )
            else:
                last_suggestion["updated_filters_string"] = (
                    "Updated Filter: "
                    + ", ".join(last_suggestion["modified_filters"])
                    + "\n"
                )

            if already_suggested_list[-1] == "industry_combo_filters":
                industry_flag = True
            else:
                industry_flag = False

            last_suggestion["promptId"] = prompt_id

        all_string_content.append(str(result))
        all_string_content.append("\n")

    if industry_flag_:
        industry_flag = True

    if all_string_content:
        all_string_content.append(f"</Result-{index}>\n")
        complete_string += "\n".join(all_string_content)

    if complete_string:
        clarification = True

    return (
        complete_string,
        aisearches,
        industry_flag,
        last_aisearch,
        last_suggestion,
        clarification,
        questions,
        and_question_asked,
        already_suggested_list,
    )


async def filters_modification_in_db(
    conversation_id, prompt_id, response_id, prompt, value
):
    query = f"""
        SELECT result
        FROM single_entity_aisearch_new
        WHERE conversation_id = '{conversation_id}'
        AND prompt_id = '{prompt_id}'
        AND response_id = '{response_id}'
        order by response_id
    """

    result_all = await postgres_fetch(query)
    if result_all:
        result = result_all[0]
        result["AI_Search_Results"] = value.get("AI_Search_Results", {})
        result_json = result
    else:
        result_json = value

    insert_query = text(
        """
        INSERT INTO single_entity_aisearch_new (conversation_id, prompt_id, response_id, prompt, result)
        VALUES (:conversation_id, :prompt_id, :response_id, :prompt, :result)
        ON CONFLICT (conversation_id, prompt_id, response_id)
        DO UPDATE SET result = EXCLUDED.result;
    """
    ).bindparams(
        bindparam("result", type_=JSONB)  # 💥 Let SQLAlchemy/asyncpg handle it
    )

    insert_params = {
        "conversation_id": conversation_id,
        "prompt_id": prompt_id,
        "response_id": response_id,
        "prompt": prompt,
        "result": result_json,
    }
    success = await postgres_insert_custom_for_filters(insert_query, insert_params)
    return True if success else False


async def possible_suggestion_filters_companyTimeline(convId, promptId):
    query = f"""
        SELECT response_id, result
        FROM single_entity_aisearch_new_temp
        WHERE conversation_id = '{convId}'
        AND prompt_id = '{promptId-1}'
        AND response_id IN ('-122')
    """

    rows = await postgres_fetch_custom(query)
    if not rows:
        return None

    result_map = {str(row[0]): row[1] for row in rows}

    for index in range(2):
        if "-122" in result_map:
            result = result_map["-122"]
            return result.get("selected_filters", {})

        await asyncio.sleep(1.5)

        rows = await postgres_fetch_custom(query)
        result_map = {row[0]: row[1] for row in rows}

    return None


async def possible_suggestion_filters(convId, promptId):
    query = f"""
        SELECT response_id, result
        FROM single_entity_aisearch_new_temp
        WHERE conversation_id = '{convId}'
        AND prompt_id = '{promptId}'
        AND response_id IN ('-2', '-15', '-14')
    """

    rows = await postgres_fetch_custom(query)
    if not rows:
        return None

    result_map = {str(row[0]): row[1] for row in rows}

    if "-2" in result_map:
        result = result_map["-2"]
        try:
            if result.get("await_task_key"):
                filters = await ASYNC_TASKS.get(result["await_task_key"])
                filters = filters.get("selected_filters", {})
                if isinstance(filters, dict):
                    return filters
            else:
                return result.get("selected_filters", {})

        except:
            pass  # Fall back to next available

    for index in range(3):
        if "-15" in result_map:
            result = result_map["-15"]
            return result.get("selected_filters", {})

        # if "-14" in result_map:
        #     result = result_map["-14"]
        #     messages =  result.get("messages", [])
        #     if not index:
        #         ali_task = asyncio.create_task(ali_function(messages))

        await asyncio.sleep(1.5)

        rows = await postgres_fetch_custom(query)
        result_map = {row[0]: row[1] for row in rows}

    return None


async def profile_count_modification_in_db(
    conversation_id, prompt_id, response_id, prompt, value
):
    query = f"""
        SELECT result
        FROM single_entity_aisearch_new
        WHERE conversation_id = '{conversation_id}'
        AND prompt_id = '{prompt_id}'
        AND response_id = '{response_id}'
        order by response_id
    """

    result_all = await postgres_fetch(query)
    result = result_all[0]
    result["profile_count"] = value

    result_json = json.dumps(result)

    prompt = prompt.replace("'", "''")

    update_query = f"""
        INSERT INTO single_entity_aisearch_new (conversation_id, prompt_id, response_id, prompt, result)
        VALUES ('{conversation_id}', '{prompt_id}', '{response_id}', '{prompt}', '{result_json}'::jsonb)
        ON CONFLICT (conversation_id, prompt_id, response_id)
        DO UPDATE SET result = EXCLUDED.result;
    """
    success = await postgres_insert(update_query)
    return True if success else False


async def update_value_publicIdentifiers(
    conversation_id, prompt_id, response_id_temp, identifier, es_client
):

    query = f"""
        SELECT result, prompt, response_id
        FROM single_entity_aisearch_new_temp
        WHERE conversation_id = '{conversation_id}' 
        AND prompt_id = '{prompt_id}'
        AND response_id >= {response_id_temp}
        order by response_id
    """

    result_all = await postgres_fetch_custom(query)
    if not result_all:
        yield ""
        return
    else:
        tasks = []
        ENTITY_NUM = None
        SIMILAR_PROFILES_FLAG = False

        for result_temp in result_all:
            result = []
            value = result_temp[0]
            main_query = result_temp[1]
            response_id = result_temp[2]

            if response_id == response_id_temp:
                ENTITY_NUM = value.get("Entity_Number", None)

            if (
                value.get("Entity_Number", None)
                and value.get("Entity_Number") != ENTITY_NUM
            ):
                break
            if value.get("Person_Modal", None) and value["Person_Modal"]:
                value["Person_Modal"]["identifier"] = identifier
                value["Person_Modal"]["response_id"] = response_id
                if value["Person_Modal"].get("sub_section", "") == "similar_profiles":
                    SIMILAR_PROFILES_FLAG = True
                yield last_converter(value["Person_Modal"])
                result.append(value)
            elif "step" in value:
                step_name = value.get("step", "")

                if step_name == "text_line_description":
                    explanation = await summary_text(
                        identifier,
                        "person",
                        "",
                        main_query,
                        es_client,
                        SIMILAR_PROFILES_FLAG,
                    )  # value.get("SUB_SECTION", "")
                    sum_of_text = ""
                    if explanation:
                        async for chunk in stream_openai_text(explanation):
                            return_payload = {
                                "step": "text_line",
                                "text": chunk,
                                "response_id": response_id,
                            }
                            yield last_converter(return_payload)
                            sum_of_text += chunk

                        yield last_converter(
                            {
                                "step": "text_line",
                                "text": "\n\n",
                                "response_id": response_id,
                            }
                        )

                    result.append({"Text Shown": sum_of_text})

                elif step_name == "text_line":
                    sum_of_text = ""
                    async for chunk in stream_openai_text(value.get("text", "")):
                        return_payload = {
                            "step": "text_line",
                            "text": chunk,
                            "response_id": response_id,
                        }
                        sum_of_text += chunk
                        yield last_converter(return_payload)
                    result.append({"Text Shown": sum_of_text})

            if response_id == response_id_temp:
                result_json = json.dumps(value).replace("'", "''")
                update_query = f"""
                    UPDATE single_entity_aisearch_new
                    SET result = '{result_json}'::jsonb
                    WHERE conversation_id = '{conversation_id}'
                    AND prompt_id = '{prompt_id}'
                    AND response_id = '{response_id}';
                """
                tasks.append(asyncio.create_task(postgres_insert(update_query)))
            else:
                tasks.append(
                    asyncio.create_task(
                        insert_into_cache_single_entity_results(
                            conversation_id,
                            prompt_id,
                            response_id,
                            main_query,
                            result[0],
                        )
                    )
                )

        if tasks:
            await asyncio.gather(*tasks)


async def fetch_processed_suggestions_preparations_from_db(
    conversation_id, prompt_id, demoBlocked
):
    query1 = f"""
        SELECT result, prompt, response_id
        FROM single_entity_aisearch_new_temp
        WHERE conversation_id = '{conversation_id}' 
        AND prompt_id = {prompt_id}
        AND response_id = -1
    """

    query2 = f"""
            SELECT result, prompt, response_id
            FROM single_entity_aisearch_new_temp
            WHERE conversation_id = '{conversation_id}' 
            AND prompt_id = {prompt_id - 1}
            AND response_id = -1
        """
    result1 = []
    result2 = []
    result3 = None

    result1, result2, result3 = await asyncio.gather(
        postgres_fetch_custom(query1),
        postgres_fetch_custom(query2),
        fetch_from_cache_single_entity_results(conversation_id, prompt_id, demoBlocked),
    )
    already_suggested_list = []

    try:
        if isinstance(result3, tuple) and len(result3) > 0:
            already_suggested_list = result3[-1]
        if isinstance(result1, list) and len(result1) > 0:
            result1 = result1[0][0]
        if isinstance(result2, list) and len(result2) > 0:
            result2 = result2[0][0]
    except:
        print(
            "error unpacking results in fetch_processed_suggestions_preparations_from_db"
        )

    if result1:
        return result1, result1.get("already_given_suggestions", []), "result1"
    if result2:
        return result2, already_suggested_list, "result2"
    else:
        return None, already_suggested_list, "result3"


async def fetch_identified_industries_list(conversation_id, prompt_id):
    query1 = f"""
        SELECT result
        FROM single_entity_aisearch_new_temp
        WHERE conversation_id = '{conversation_id}' 
        AND prompt_id = {prompt_id - 1}
        AND response_id = -1216
    """

    result1 = await postgres_fetch_custom(query1)

    try:
        if isinstance(result1, list) and len(result1) > 0:
            result1 = result1[0][0]
            result1 = result1.get("identified_industries_list", "")
    except:
        print("error unpacking results in fetch_identified_industries_list")

    if result1:
        return result1
    else:
        {}
