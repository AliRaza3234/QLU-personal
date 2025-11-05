from app.utils.fastmode.postgres_functions import (
    insert_into_cache_single_entity_results,
)
from app.utils.qlu2_features.aisearch.question_answers.qa_prompts import (
    Industry_Breakdown_Prompt,
    Pureplay_Prompt,
    Industry_Pureplay_Both_Prompt,
    General_Ambiguity_ONLY_Prompt,
    General_Ambiguity_Prompt,
    Updated_Phrasing_Prompt,
    Client_Company_Only_Instructions,
    Client_Company_Plus_Industry_Breakdown_Instructions,
    Client_Company_industry_missing_question_Instructions,
    AMBIGUOUS_AND_SCENARIO_QUESTION_SYSTEM,
    TIMELIME_SELECTION_ANALYSIS_PROMPT_SYSTEM,
    AMBIGUOUS_TIMELINE_DETECTION_SYSTEM,
    INDUSTRY_QUESTION_GUARDRAIL_PROMPT,
    INDUSTRY_LEVELS_AND_QUESTIONS_PROMPT,
    INTENT_AND_TARGET_ANALYSIS_PROMPT,
    RECRUITMENT_QUERY_QUESTIONS_SYSTEM,
    TITLE_STEP_UP_DOWN_VARIATION_PROMPT,
    RECRUITMENT_QUERY_GUARDRAIL_PROMPT,
    PUREPLAY_VERDICT_AND_QUESTION_SYSTEM,
    AMBIGUITY_FOLLOW_UP_SYSTEM,
    AMBIGUITY_CLEAR_PROMPT_SYSTEM,
    NO_DEMO_AMBIGUITY_FOLLOW_UP_SYSTEM,
    NO_DEMO_AMBIGUITY_CLEAR_PROMPT_SYSTEM,
    GENERATION_SYSTEM_PROMPT,
    GENERATION_SYSTEM_PROMPT_NON_REASONING,
    EXECUTIVE_QUERY_DETECTION_SYSTEM,
    INDUSTRY_DETECTOR_FROM_STREAM_PROMPT,
)

from app.utils.qlu2_features.aisearch.utilities.llm_functions.llms import (
    call_llama_70b,
    call_gpt_oss_120b,
    call_claude_sonnet,
    call_gpt_4_1,
    call_gpt_4_1_mini,
    call_groq_llama_scout,
    call_gpt_oss_20b,
)
from app.utils.qlu2_features.aisearch.utilities.helper_functions.misc_functions import (
    extract_generic,
    extract_marker,
    extract_and_format_names,
)

from app.utils.qlu2_features.aisearch.utilities.helper_functions.postgres_functions import (
    fetch_from_cache_single_entity_results,
    fetch_identified_industries_list,
)

from app.utils.qlu2_features.aisearch.utilities.general.fast_utils import (
    get_full_context,
)

import asyncio
import json

from app.utils.qlu2_features.aisearch.constants.shared_state import ASYNC_TASKS


async def generate_reply_agent(
    convId,
    promptId,
    main_query,
    string_second_string="",
    last_suggestion="",
    questions="",
    demoBlocked=False,
):

    second_string_clear_prompt = """
    ## IMPORTANT INSTRUCTIONS TO TAKE INTO ACCOUNT:
    * **If the user has been asked a follow-up question by the system, analyze the <Last_Query> and identify what they answered and what they didn't and just rewrite the clear_prompt in words as close to what the user has said**. Take the previous conversation into account; if the new prompt can be a continuation, it likely is one. The clear prompt MUST contain the context of previous chats as well if any of the previous chat was relevant.
    * **If the user was asked a question by the system and they haven't answered, and ignored them, then do NOT include anything that they ignored in the clear prompt**
    * **If the <Last_Query> contains a modification command to add specific filters, or remove certain filters, e.g., "change timeline to past", "remove experience filter", or other similar commands then you must analyze carefully and remove, add, or update the relevant parts of the clear prompt.**
    * **If the user was asked about a follow-up about interested industry segments, and they answer it, by mentioning all segments, of picks some segments, or choose some segments and add others, then you must carefully analyze this answer and then write the clear prompt accordingly. **
        * If all segments are mentioned, then write each and every segment asked in the question in the clear prompt.
        * If user picks some specific segments, then only write those segments in the clear prompt.
        * While writing the chosen segments, you need to identify the company names mentioned along with the segments.
        * If there's a mention of company names examples, you **must always include those company names along with the selected segments, while writing the clear prompt**
        * If user mentions any company name(s) to exclude, then you should **only exclude the company name mentioned AND MUST KEEP the other company names not excluded in the clear prompt**, and **must make sure to NOT exclude other company names in the chosen segments**.
        * **ALWAYS make sure to write the exclusions explicitly.**
    """

    follow_up_system_second_string = ""

    if demoBlocked:
        FOLLOW_UP_SYSTEM = NO_DEMO_AMBIGUITY_FOLLOW_UP_SYSTEM
        CLEAR_PROMPT_SYSTEM = NO_DEMO_AMBIGUITY_CLEAR_PROMPT_SYSTEM
    else:
        FOLLOW_UP_SYSTEM = AMBIGUITY_FOLLOW_UP_SYSTEM
        CLEAR_PROMPT_SYSTEM = AMBIGUITY_CLEAR_PROMPT_SYSTEM

    AND_SCENARIO_QUESTION_SYSTEM = AMBIGUOUS_AND_SCENARIO_QUESTION_SYSTEM
    CONDITIONAL_INDSTRUCTIONS_STRING = ""

    if string_second_string:

        follow_up_system_second_string = """
        ## IMPORTANT INSTRUCTIONS TO TAKE INTO ACCOUNT:
        - **If the user has been asked a follow-up question by the system before and they haven't answered, do NOT ask them again. Take the previous conversation into account; if the new prompt can be a continuation, it likely is one. 
        - **If the <Last_Query> contains a modification command to add specific filters, or remove certain filters, e.g., "change timeline to past", "remove experience filter", or other similar commands then you **MUST NOT ask the question at all**.**
        -  **If the command is about removing specific filters, then YOU MUST NOT ASK ANY QUESTION. The only time you can ask question on modification command is when modification commands ask to 'remove **all** filters'. **ONLY In that case**, you can ask: "Let me know if there is anything else you would like to add to the search?"* and the applicable scenario would be the "Modification_Command" scenario.**"""

        CLEAR_PROMPT_SYSTEM += second_string_clear_prompt
        AND_SCENARIO_QUESTION_SYSTEM += follow_up_system_second_string

        if questions:
            if (
                "Industry" in questions
                and "client_company" not in questions
                and "Pure Play" not in questions
            ):
                CONDITIONAL_INDSTRUCTIONS_STRING += Industry_Breakdown_Prompt
            elif "client_company" in questions and "Industry" in questions:
                CONDITIONAL_INDSTRUCTIONS_STRING += (
                    Client_Company_Plus_Industry_Breakdown_Instructions
                )
            elif "client_company" in questions and "industry" in questions:
                CONDITIONAL_INDSTRUCTIONS_STRING += (
                    Client_Company_industry_missing_question_Instructions
                )

            if "Pure Play" in questions and "Industry" not in questions:
                CONDITIONAL_INDSTRUCTIONS_STRING += Pureplay_Prompt
            elif "Pure Play" in questions and "Industry" in questions:
                CONDITIONAL_INDSTRUCTIONS_STRING += Industry_Pureplay_Both_Prompt

            if "Ambiguity" in questions:
                if len(questions) == 1:
                    CONDITIONAL_INDSTRUCTIONS_STRING += General_Ambiguity_ONLY_Prompt
                else:
                    CONDITIONAL_INDSTRUCTIONS_STRING += General_Ambiguity_Prompt

        CLEAR_PROMPT_SYSTEM += Updated_Phrasing_Prompt

        follow_up_user_prompt = f"""<Whole_Conversation>\n{string_second_string}<Last_Query>\n{main_query}\n</Last_Query>\n<Whole_Conversation>\n 
        ## FINAL INSTRUCTIONS TO KEEP IN MIND:
        - Always take into account the full context of the conversation, including all previous queries, results, and system-generated follow-ups. 
        - If the new query is a response to a previous follow-up by another agent, treat it as a continuation.
        - Do not repeat questions that have already been asked, especially those regarding ambiguity 
        — if the user has not responded to a previous ambiguity-related question, assume ambiguity=0 and do not ask any question. However if the user asks for explanation then rephrase in simple words what was asked before.
        - Think logically about how the latest input relates to earlier ones, and only drop context if it is certain the new message is unrelated. 
        - Review the <Last_Query> for any new information. 
        - If <Last_Query> makes it essential to clarify the ambiguity, you should ask for those specific details. Otherwise, do not ask.\n{follow_up_system_second_string}"""

        clear_prompt_user_prompt = f"""<Whole_Conversation>\n{string_second_string}<Last_Query>\n{main_query}\n</Last_Query>\n<Whole_Conversation>\n 
        ## FINAL INSTRUCTIONS TO KEEP IN MIND:
        - Always take into account the full context of the conversation, including all previous queries, results, and system-generated follow-ups. 
        - If the new query is a response to a previous follow-up by another agent, treat it as a continuation and construct the new clear prompt using all relevant context. 
        — if the user has not responded to a previous ambiguity-related question, proceed by forming a clear prompt that closely mirrors the user’s wording across the conversation.
        - Think logically about how the latest input relates to earlier ones.
        - Since the final clear prompt drives the backend results, it **must fully reflect the conversation’s evolving intent**. 
        - Review the <Last_Query> for any new information.\n{second_string_clear_prompt}"""

        if last_suggestion:
            follow_up_user_prompt += """If the user asks what refining the search means, can follow_up with them how they'd like to narrow or adjust the search."""
    else:
        follow_up_user_prompt = f"""<User_Prompt>\n{main_query}\n</User_Prompt>"""
        clear_prompt_user_prompt = f"""<User_Prompt>\n{main_query}\n</User_Prompt>"""

    CONDITIONAL_INDSTRUCTIONS_STRING += Client_Company_Only_Instructions

    follow_up_messages = [
        {
            "role": "system",
            "content": FOLLOW_UP_SYSTEM.replace(
                "{{MODIFICATION_SCENARIOS}}", follow_up_system_second_string
            ),
        },
        {
            "role": "user",
            "content": follow_up_user_prompt,
        },
    ]

    clear_prompt_messages = [
        {
            "role": "system",
            "content": CLEAR_PROMPT_SYSTEM.replace(
                "{{modifications}}", CONDITIONAL_INDSTRUCTIONS_STRING
            ),
        },
        {
            "role": "user",
            "content": clear_prompt_user_prompt,
        },
    ]

    follow_up_response_task = asyncio.create_task(
        call_gpt_4_1(
            messages=follow_up_messages,
            temperature=0.1,
        )
    )

    clear_prompt_response_task = asyncio.create_task(
        call_gpt_4_1(
            messages=clear_prompt_messages,
            temperature=0.1,
        )
    )

    clear_prompt_response = ""
    mapped_questions_list = []

    follow_up_response = await follow_up_response_task

    question_type_mapping = {
        1: "Generic",
        2: "Acronyms",
    }

    follow_up_questions = ""

    try:
        follow_up_response = extract_generic(
            "<Output>", "</Output>", follow_up_response
        )
        follow_up_response = json.loads(follow_up_response)
        mapped_questions_list = follow_up_response.get("questions", [])

    except:
        follow_up_response = {"parsing_failed": True}

    if follow_up_response.get("ambiguity", 0) == 1:

        follow_up_questions += f"\n{follow_up_response.get('follow_up', '')}"

        if mapped_questions_list:
            mapped_questions_list = [
                question_type_mapping.get(q, q) for q in mapped_questions_list
            ]

        return {
            "ambiguity": 1,
            "follow_up": follow_up_questions,
            "questions": mapped_questions_list,
        }

    else:
        clear_prompt_response = await clear_prompt_response_task

        asyncio.create_task(
            insert_into_cache_single_entity_results(
                conversation_id=convId,
                prompt_id=promptId,
                response_id=-1261,
                prompt=main_query,
                result={
                    "clear_prompt_response": clear_prompt_response,
                    "clear_prompt_messages": clear_prompt_messages,
                },
                temp=True,
            )
        )

        clear_prompt_response = extract_generic(
            "<clear_prompt>", "</clear_prompt>", clear_prompt_response
        )
        if clear_prompt_response:
            clear_prompt_response = clear_prompt_response.strip()
        else:
            clear_prompt_response = ""

        return {"ambiguity": 0, "clear_prompt": clear_prompt_response, "questions": []}


async def timeline_selection_analysis_agent(conversation_context):
    messages = [
        {"role": "system", "content": TIMELIME_SELECTION_ANALYSIS_PROMPT_SYSTEM},
        {
            "role": "user",
            "content": f"Conversation: {conversation_context}",
        },
    ]

    response = await call_llama_70b(
        messages=messages,
        temperature=0.1,
    )

    timeline_mapping = {
        "CURRENT_AND_PAST": "AND",
        "CURRENT_OR_PAST": "OR",
        "CURRENT_ONLY": "CURRENT",
        "PAST_ONLY": "PAST",
        "NOT_SELECTED": "NOT_SELECTED",
    }

    selected_timeline = extract_generic(
        "<Selected_Timeline>", "</Selected_Timeline>", response
    )
    selected_timeline = timeline_mapping.get(selected_timeline, "NOT_SELECTED")
    modifications = extract_generic("<Modifications>", "</Modifications>", response)
    dict_to_return = {
        "no_relevant_answer": False,
        "selected_timeline": "NOT_SELECTED",
        "modifications": False,
    }

    if selected_timeline == "NOT_SELECTED" and modifications == "0":
        return {
            "no_relevant_answer": True,
            "selected_timeline": "NOT_SELECTED",
            "modifications": False,
        }

    if selected_timeline != "NOT_SELECTED":
        dict_to_return["selected_timeline"] = selected_timeline

    if modifications == "1":
        dict_to_return["modifications"] = True

    return dict_to_return


async def and_timeline_ambiguity_detection_agent(conversation_context):
    messages = [
        {"role": "system", "content": AMBIGUOUS_TIMELINE_DETECTION_SYSTEM},
        {
            "role": "user",
            "content": f"Conversation: {conversation_context}",
        },
    ]

    response = await call_gpt_4_1(
        messages=messages,
        temperature=0.1,
    )

    ambiguity = extract_generic("<ambiguity>", "</ambiguity>", response)
    if ambiguity == "1":
        return {
            "ambiguity": 1,
        }
    else:
        return {
            "ambiguity": 0,
        }


async def industry_question_guardrail_agent(context, identified_industries_str):
    messages = [
        {"role": "system", "content": INDUSTRY_QUESTION_GUARDRAIL_PROMPT},
        {
            "role": "user",
            "content": f"Here is the Conversation Context: \n\n{context}\n\nHere are the already asked industries targets **WHICH YOU DO NOT NEED TO REPEAT**: <already_asked_industries>\n\n{identified_industries_str}</already_asked_industries>",
        },
    ]

    response = await call_gpt_oss_120b(
        messages=messages,
        temperature=0.1,
    )

    parsed_response = extract_marker(response, marker="</reasoning>", position="after")

    need_to_ask_question = extract_generic(
        "<need_to_ask_question>", "</need_to_ask_question>", parsed_response
    )
    if need_to_ask_question == "0":
        return {"need_to_ask_question": False, "response": response}
    else:
        return {"need_to_ask_question": True, "response": response}


async def intent_and_target_analysis_agent(
    context, already_identified_targets, hiring_company_instruction
):
    if hiring_company_instruction:
        hiring_company_instruction = "        #### IMPORTANT INSTRUCTION FOR SPECIFIC COMPANY NAME MENTIONED: Careful Handling of Specific Company Name Mentioned is Required. User has been asked a question about which company are they recruiting for i.e., Hiring Company, So if in the <Last_Query>, user mentions any specific company name, it is most probably in answer to the question about which companies they are recruiting for. Make sure to distinguish whether it is the hiring company or the target company. **Do not confuse hiring company with target company.**)"
    else:
        hiring_company_instruction = ""

    messages = [
        {
            "role": "system",
            "content": INTENT_AND_TARGET_ANALYSIS_PROMPT.replace(
                "{{CLIENT_COMPANY_MENTIONED}}", hiring_company_instruction
            ),
        },
        {
            "role": "user",
            "content": f"Here is the Conversation Context: \n\n{context} , Here are the already_identified_targets: <already_identified_targets>{already_identified_targets}</already_identified_targets>",
        },
    ]
    response = await call_gpt_oss_120b(
        messages=messages,
        temperature=0.1,
    )

    parsed_response = extract_marker(response, marker="</reasoning>", position="after")

    identified_industries_list = ""
    bullet_all_targets_list = ""
    redflag = extract_generic(
        "<category_of_case>", "</category_of_case>", parsed_response
    )
    all_targets = extract_generic("<new_targets>", "</new_targets>", parsed_response)
    identified_industries_boolean = extract_generic(
        "<targets_identified_boolean>", "</targets_identified_boolean>", parsed_response
    )
    if identified_industries_boolean:
        identified_industries_boolean = identified_industries_boolean.strip()
        if identified_industries_boolean == "1" and all_targets:
            bullet_all_targets_list = extract_and_format_names(all_targets)
            if bullet_all_targets_list:
                identified_industries_list = bullet_all_targets_list

    if redflag:
        redflag = redflag.strip()
    if redflag == "1" or not bullet_all_targets_list:
        return {"response": response, "redflag": True, "identified_industries_list": ""}
    else:
        return {
            "response": response,
            "redflag": False,
            "identified_industries_list": identified_industries_list,
        }


async def industry_levels_and_questions_agent(targets):
    messages = [
        {"role": "system", "content": INDUSTRY_LEVELS_AND_QUESTIONS_PROMPT},
        {
            "role": "user",
            "content": f"<Analyzed Targets and their Reasoning>{targets}</Analyzed Targets and their Reasoning>",
        },
    ]
    response = await call_gpt_oss_120b(
        messages=messages,
        temperature=0.1,
    )

    parsed_response = extract_marker(response, marker="</reasoning>", position="after")

    need_to_ask_question = extract_generic(
        "<need_to_ask_question>", "</need_to_ask_question>", parsed_response
    )

    returned_question = ""
    if need_to_ask_question:
        need_to_ask_question = need_to_ask_question.strip()
        if need_to_ask_question == "1":
            question = extract_generic("<question>", "</question>", parsed_response)
            if question and isinstance(question, str):
                returned_question = question.strip()

    return {"question": returned_question}


async def recruitment_query_guardrails_agent(context, clarification=False):
    messages = [
        {"role": "system", "content": RECRUITMENT_QUERY_GUARDRAIL_PROMPT},
        {"role": "user", "content": f"Here is the Conversation Context: \n\n{context}"},
    ]
    response = await call_gpt_oss_120b(
        messages=messages,
        temperature=0.1,
    )

    parsed_response = extract_marker(response, marker="</reasoning>", position="after")
    need_to_ask_question = extract_generic(
        "<need_to_ask_question>", "</need_to_ask_question>", parsed_response
    )

    if need_to_ask_question == "0":
        return {"need_to_ask_question": False}
    else:
        return {"need_to_ask_question": True}


async def recruitement_query_questions_agent(context):
    messages = [
        {"role": "system", "content": RECRUITMENT_QUERY_QUESTIONS_SYSTEM},
        {"role": "user", "content": f"Here is the Conversation Context: \n\n{context}"},
    ]
    response = await call_gpt_oss_120b(
        messages=messages,
        temperature=0.1,
    )

    return_json = {}

    criteria_map = {
        "Target Industries": "industry",
        "Client Company": "client_company",
        "Skills": "skills",
        "Level Variation of Title": "title",
    }
    parsed_response = extract_marker(response, marker="</reasoning>", position="after")
    try:
        output_json = extract_generic(
            "<output_json>", "</output_json>", parsed_response
        )
        output_json = json.loads(output_json)
        if isinstance(output_json, dict):
            # logic to correctly map questions:
            for item in output_json["missing_information"]:
                return_json[criteria_map[item["criterion"]]] = item["question"]

    except Exception as e:
        print(e)

    return return_json


async def title_step_up_down_variation_question_agent(context):
    messages = [
        {"role": "system", "content": TITLE_STEP_UP_DOWN_VARIATION_PROMPT},
        {"role": "user", "content": f"Here is the Conversation Context: \n\n{context}"},
    ]
    response = await call_gpt_oss_120b(
        messages=messages,
        temperature=0.1,
    )

    ambiguous_acronyms_question = extract_generic(
        "<ambiguous_acronyms_question>", "</ambiguous_acronyms_question>", response
    )
    suggested_titles_question = extract_generic(
        "<suggested_titles_question>", "</suggested_titles_question>", response
    )

    return_json = {}

    if ambiguous_acronyms_question:
        return_json["acronym"] = ambiguous_acronyms_question.strip()

    if suggested_titles_question:
        return_json["title_variation"] = suggested_titles_question.strip()

    return return_json


async def get_recruitment_query_questions(context, clarification):
    question_generation_task = asyncio.create_task(
        recruitement_query_questions_agent(context)
    )
    title_question_task = asyncio.create_task(
        title_step_up_down_variation_question_agent(context)
    )
    guardrails_response = await recruitment_query_guardrails_agent(
        context, clarification
    )

    return_json = {}

    if guardrails_response.get("need_to_ask_question", ""):
        return_json = await question_generation_task
        title_questions = await title_question_task
        return_json["recruitment_question"] = 1
        if title_questions:
            return_json.update(title_questions)
    else:
        return_json["recruitment_question"] = 0

    return return_json


async def pureplay_verdict_and_question_agent(user_query, company_list):
    messages = [
        {"role": "system", "content": PUREPLAY_VERDICT_AND_QUESTION_SYSTEM},
        {
            "role": "user",
            "content": f"<user_query>{user_query}</user_query>\n<companies_list>{company_list}</companies_list>",
        },
    ]
    response = await call_gpt_oss_120b(
        messages=messages,
        temperature=0.1,
    )
    verdict = extract_generic("<verdict>", "</verdict>", response)
    question = extract_generic("<question>", "</question>", response)
    if question:
        question = question.strip()
    return {"response": response, "verdict": verdict, "question": question}


async def company_generation_list_agent(target_industry, reasoning=False):
    if reasoning:
        system_prompt = GENERATION_SYSTEM_PROMPT
    else:
        system_prompt = GENERATION_SYSTEM_PROMPT_NON_REASONING
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"Here is the analysis of the targeting companies and industries: {target_industry}",
        },
    ]

    response = await call_gpt_oss_120b(messages=messages, temperature=0.1)
    return {"companies_list": response}


async def new_pureplay_question_agent(targets_coro):
    targets, identified_industries_list = await targets_coro
    if targets is None:
        return {"pureplay_question": "", "question": 0}

    companies_list = await company_generation_list_agent(targets, reasoning=True)
    pureplay_verdict_and_question_response = await pureplay_verdict_and_question_agent(
        targets, companies_list.get("companies_list", "")
    )

    question = ""

    if pureplay_verdict_and_question_response.get("question", ""):
        question = pureplay_verdict_and_question_response.get("question", "")

    return {
        "pureplay_question": question,
        "identified_industries_list": identified_industries_list,
    }


async def pre_questions_coro(
    context, identified_industries_str, clarification, hiring_company_instruction
):
    targets_task = asyncio.create_task(
        intent_and_target_analysis_agent(
            context, identified_industries_str, hiring_company_instruction
        )
    )
    if clarification:
        guardrails_response = await industry_question_guardrail_agent(
            context, identified_industries_str
        )
        need_to_ask_question = guardrails_response["need_to_ask_question"]
    else:
        need_to_ask_question = True
        guardrails_response = ""

    if not need_to_ask_question:
        return None, {}
    targets = await targets_task
    redflag = targets["redflag"]
    identified_industries_list = targets.get("identified_industries_list", "")
    if redflag:
        return None, {}

    return targets.get("response", None), identified_industries_list


async def new_industry_question_agent(targets_coro):
    targets, identified_industries_list = await targets_coro
    if targets is None:
        return {"industry_question": "", "question": 0}

    returned_question = ""

    industry_question_response = await industry_levels_and_questions_agent(targets)

    if industry_question_response.get("question", ""):
        returned_question = industry_question_response.get("question", "")

    return {
        "industry_question": returned_question,
        "identified_industries_list": identified_industries_list,
    }


async def executive_query_detection_agent(query):
    messages = [
        {"role": "system", "content": EXECUTIVE_QUERY_DETECTION_SYSTEM},
        {"role": "user", "content": f"Here is the query: {query}"},
    ]
    response = await call_gpt_oss_120b(messages=messages, temperature=0.1)

    verdict = extract_generic("<verdict>", "</verdict>", response)

    executive_query_detected = False

    if verdict:
        verdict = verdict.strip()
        if verdict == "1":
            executive_query_detected = True

    return executive_query_detected


async def industry_detection_from_input_stream_agent(
    convId, promptId, new_text, demoBlocked=False
):
    # Get context:
    event_key = f"{convId}_{promptId}_industry_detection_event"
    event = asyncio.Event()
    ASYNC_TASKS[event_key] = event

    # cache_storage_key for industry stream
    industry_stream_key = f"{convId}_{promptId}_industry_stream"
    current_state = ASYNC_TASKS.get(industry_stream_key, None)

    # reference key for industry question coroutine
    industry_question_task_key = f"{convId}_{promptId}_industry_question_task"

    processed_text = ""
    previous_company_industry_information = ""
    parsed_reply = {}

    if current_state:
        processed_text = current_state.get("processed_text", "")
        previous_company_industry_information = current_state.get(
            "previous_company_industry_information", ""
        )

    input_dict = {
        "previous_company_industry_information": previous_company_industry_information,
        "processed_text": processed_text,
        "complete_string_with_new_text": new_text,
    }

    messages = [
        {"role": "system", "content": INDUSTRY_DETECTOR_FROM_STREAM_PROMPT},
        {"role": "user", "content": f"Here is the input: {input_dict}"},
    ]
    response = await call_gpt_oss_20b(messages=messages, temperature=0.1)

    try:
        parsed_reply = json.loads(response)
    except Exception as e:
        print(e)
        return False

    if not parsed_reply:
        parsed_reply = {}

    previous_company_industry_information = parsed_reply.get(
        "updated_company_industry_information", []
    )
    action = parsed_reply.get("action", "")

    if action == "1":
        # call industry question task
        industry_question_task = asyncio.create_task(
            create_industry_breakdown_question_task(
                convId, promptId, new_text, demoBlocked
            )
        )
        ASYNC_TASKS[f"{industry_question_task_key}"] = industry_question_task
        event.set()
    else:
        event.set()

    output_dict = {
        "previous_company_industry_information": previous_company_industry_information,
        "processed_text": new_text,
    }

    ASYNC_TASKS[industry_stream_key] = output_dict

    return True


async def create_industry_breakdown_question_task(
    convId, promptId, text, demoBlocked=False
):

    db_variables_key = f"{convId}_{promptId}_db_variables"

    input_variables_dict = {
        "context": "",
        "identified_industries_str": "",
        "clarification": False,
        "hiring_company_instruction": False,
    }

    if promptId > 1:
        if db_variables_key not in ASYNC_TASKS:
            identified_industries_str_task = asyncio.create_task(
                fetch_identified_industries_list(convId, promptId)
            )
            (
                string_second_string,
                aisearch,
                industry_flag,
                last_aisearch,
                last_suggestion,
                clarification,
                questions,
                company_question,
                already_suggested_list,
            ) = await fetch_from_cache_single_entity_results(
                convId, promptId, demoBlocked
            )
            identified_industries_str = await identified_industries_str_task
            if not identified_industries_str:
                identified_industries_str = ""

            input_variables_dict["context"] = string_second_string
            input_variables_dict["identified_industries_str"] = (
                identified_industries_str
            )
            input_variables_dict["clarification"] = clarification
            input_variables_dict["hiring_company_instruction"] = company_question
            ASYNC_TASKS[db_variables_key] = input_variables_dict
        else:
            input_variables_dict = ASYNC_TASKS[db_variables_key]

    context = await get_full_context(input_variables_dict["context"], text)

    targets_coro = asyncio.create_task(
        pre_questions_coro(
            context=context,
            identified_industries_str=input_variables_dict["identified_industries_str"],
            clarification=input_variables_dict["clarification"],
            hiring_company_instruction=input_variables_dict[
                "hiring_company_instruction"
            ],
        )
    )
    new_industry_question = await new_industry_question_agent(targets_coro)
    return new_industry_question
