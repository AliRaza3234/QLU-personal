from app.utils.fastmode.prompts import (
    INDUSTRY_QUESTION_SYSTEM,
    INDUSTRY_QUESTION_USER,
    ACRONYM_SYSTEM,
    ACRONYM_USER,
    AI_SEARCH_QA_PROMPT_SYSTEM,
    AI_SEARCH_QA_PROMPT_USER,
    D2_QUESTION_SYSTEM_PROMPT,
    D2_QUESTION_USER_PROMPT,
    INDUSTRY_DO_NOT_REPEAT_QUESTION_GUIDELINES,
    Industry_Breakdown_Prompt,
    Pureplay_Prompt,
    Industry_Pureplay_Both_Prompt,
    General_Ambiguity_ONLY_Prompt,
    General_Ambiguity_Prompt,
    Proper_Phrasing_Prompt,
    Updated_Phrasing_Prompt,
    AMBIGUOUS_AND_SCENARIO_QUESTION_SYSTEM,
    TIMELIME_SELECTION_ANALYSIS_PROMPT_SYSTEM,
    AMBIGUOUS_TIMELINE_DETECTION_SYSTEM,
    INDUSTRY_BREAKDOWN_QUESTION_AGENT_SYSTEM,
    INDUSTRY_QUESTION_GUARDRAIL_PROMPT,
    INDUSTRY_LEVELS_AND_QUESTIONS_PROMPT,
    INTENT_AND_TARGET_ANALYSIS_PROMPT,
    PURE_PLAY_QUESTION,
    RECRUITMENT_QUERY_QUESTIONS_SYSTEM,
    RECRUITMENT_QUERY_GUARDRAIL_PROMPT,
    PUREPLAY_GENERATOR_SYSTEM,
    PUREPLAY_VERDICT_AND_QUESTION_SYSTEM,
)

from qutils.openrouter.router import llm_async
from app.utils.fastmode.helper_functions import extract_generic
from app.utils.fastmode.helper_functions import last_converter
import asyncio
import json


async def industry_clarification_question_agent(conversation_context):
    messages = [
        {
            "role": "system",
            "content": INDUSTRY_QUESTION_SYSTEM,
        },
        {
            "role": "user",
            "content": INDUSTRY_QUESTION_USER.replace(
                "{{conversation_context}}", conversation_context
            ),
        },
    ]
    response = await llm_async(
        messages,
        model="meta-llama/llama-3.3-70b-instruct",
        extra_body={"provider": {"order": ["groq", "cerebras"]}},
        temperature=0.1,
    )
    question = extract_generic("<question>", "</question>", response)
    need_for_question = extract_generic(
        "<need_for_question>", "</need_for_question>", response
    )

    if need_for_question:
        need_for_question = need_for_question.strip()
        if need_for_question == "Yes":
            need_for_question = True
        else:
            need_for_question = False
    else:
        need_for_question = False

    if question:
        question = question.strip()

    return {
        "question": question,
        "need_for_question": need_for_question,
        "reasoning": response,
    }


async def acronym_agent(conversation_context):
    messages = [
        {
            "role": "system",
            "content": ACRONYM_SYSTEM,
        },
        {
            "role": "user",
            "content": ACRONYM_USER.replace(
                "{{conversation_context}}", conversation_context
            ),
        },
    ]
    response = await llm_async(
        messages,
        model="meta-llama/llama-3.3-70b-instruct",
        extra_body={"provider": {"order": ["groq", "cerebras"]}},
        temperature=0.1,
    )

    question = extract_generic("<question>", "</question>", response)
    need_for_question = extract_generic(
        "<need_for_question>", "</need_for_question>", response
    )

    if question:
        question = question.strip()
    if need_for_question:
        need_for_question = need_for_question.strip()
        if need_for_question == "Yes":
            need_for_question = True
        else:
            need_for_question = False
    else:
        need_for_question = False

    return {
        "question": question,
        "need_for_question": need_for_question,
        "reasoning": response,
    }


async def acronym_industry_handling(conversation_context):
    acronym_result, industry_result = await asyncio.gather(
        *[
            acronym_agent(conversation_context),
            industry_clarification_question_agent(conversation_context),
        ]
    )

    questions = []

    if acronym_result.get("need_for_question"):
        questions.append(acronym_result.get("question"))

    if industry_result.get("need_for_question"):
        questions.append(industry_result.get("question"))

    if not questions:
        return {"question": ""}

    # Construct the string based on number of questions
    if len(questions) == 1:
        string = "Could you please help clarify the following question:\n"
    else:
        string = "Could you please help clarify the following questions:\n"

    for i, question in enumerate(questions, 1):
        if len(questions) == 1:
            string += f"{question}\n"
        else:
            string += f"{i}. {question}\n"

    return {"question": string.strip()}


# async def d2_industry_question_agent(conversation_context, respId):
#     messages = [
#         {"role": "system", "content": D2_QUESTION_SYSTEM_PROMPT},
#         {
#             "role": "user",
#             "content": D2_QUESTION_USER_PROMPT.replace(
#                 "{{conversation_context}}", conversation_context
#             ),
#         },
#     ]

#     d2_question_stream = False
#     response = ""

#     async for chunk in asynchronous_streaming_llm(
#         messages,
#         model="claude-sonnet-4-20250514",
#         provider="anthropic",
#         temperature=0.1,
#     ):
#         response += chunk
#         if d2_question_stream:
#             if "</" in chunk:
#                 last_chunk = chunk.split("</")[0]
#                 return_payload = {
#                     "step": "text_line",
#                     "text": last_chunk,
#                     "response_id": respId + 1,
#                 }
#                 yield return_payload
#                 d2_question_stream = False
#                 break
#             return_payload = {
#                 "step": "text_line",
#                 "text": chunk,
#                 "response_id": respId + 1,
#             }
#             yield return_payload

#         elif "</verdict>" in response:
#             verdict = extract_generic("<verdict>", "</verdict>", response)
#             if "True" in verdict:
#                 yield {"no_d2_question": True}
#                 break

#         if "<question>" in response and not d2_question_stream:
#             d2_question_stream = True
#             tmp_chunk = response.split("<question>")[1]
#             return_payload = {
#                 "step": "text_line",
#                 "text": tmp_chunk,
#                 "response_id": respId + 1,
#             }
#             yield return_payload


async def _await_next(iterator):
    return await iterator.__anext__()


def _as_task(iterator):
    return asyncio.create_task(_await_next(iterator))


async def d2_industry_question_agent(conversation_context):
    messages = [
        {"role": "system", "content": D2_QUESTION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": D2_QUESTION_USER_PROMPT.replace(
                "{{conversation_context}}", conversation_context
            ),
        },
    ]
    response = await llm_async(
        messages,
        model="anthropic/claude-sonnet-4",
        extra_body={
            "provider": {"order": ["anthropic", "google-vertex", "amazon-bedrock"]}
        },
        temperature=0.1,
    )

    verdict = extract_generic("<verdict>", "</verdict>", response)
    question = extract_generic("<question>", "</question>", response)

    if verdict:
        verdict = verdict.strip()
        verdict_boolean, verdict_score = verdict.split("~")
        verdict_boolean = verdict_boolean.strip().lower()
        verdict_score = int(verdict_score.strip())
        if verdict_score > 7 and verdict_boolean == "false":
            if question:
                return question.strip()
            else:
                return None
    else:
        return None


async def ai_search_questions_agent_old(
    conversation_context, clarification_question_asked=False
):

    # d2_industry_question_task = asyncio.create_task(
    #     d2_industry_question_agent(conversation_context)
    # )
    if clarification_question_asked:
        user_prompt = f"""{conversation_context}
        Always take into account the full context of the conversation, including all previous queries, results, and system-generated follow-ups.
        If the new query is a response to a previous follow-up by another agent, treat it as a continuation.
        Do not repeat questions that have already been asked, especially those regarding asking user which industry segments they are interested in.
        — if the user hasn’t responded to a previous ambiguity-related question, assume ambiguity=0. 
        MAKE SURE THAT QUESTIONS ARE NOT REPEATED.
        """
    else:
        user_prompt = conversation_context

    messages = [
        {"role": "system", "content": INDUSTRY_BREAKDOWN_QUESTION_AGENT_SYSTEM},
        {
            "role": "user",
            "content": user_prompt,
        },
    ]

    response = await llm_async(
        messages,
        model="anthropic/claude-sonnet-4",
        extra_body={
            "provider": {"order": ["anthropic", "google-vertex", "amazon-bedrock"]}
        },
        temperature=0.1,
    )

    question = extract_generic("<question>", "</question>", response)
    need_for_question = extract_generic(
        "<need_for_question>", "</need_for_question>", response
    )
    industry_levels_mapping = extract_generic(
        "<industry_levels_mapping>", "</industry_levels_mapping>", response
    )
    reason_for_no_question = extract_generic(
        "<reason_for_no_question>", "</reason_for_no_question>", response
    )

    # If no need for question, then just return in start.
    if need_for_question:
        need_for_question = need_for_question.strip()
        if need_for_question == "0":
            if reason_for_no_question:
                reason_for_no_question = reason_for_no_question.strip()
                if reason_for_no_question not in [
                    "D2_or_D3_industry_mentioned",
                    '"D2_or_D3_industry_mentioned"',
                ]:
                    return {"question": ""}
            else:
                return {"question": ""}
    else:
        return {"question": ""}

    if industry_levels_mapping:
        industry_levels_mapping = industry_levels_mapping.strip()
        industry_levels_mapping = json.loads(industry_levels_mapping)
        # If any of the industry is either d0 or d1, won't ask question on d2 industry based on title
        if any(
            value in ["D0", "D1", "D2"] for value in industry_levels_mapping.values()
        ):
            # Returning this Question because it is a D0 or D1 level industry
            return {"question": question.strip() if question else ""}
        # elif any(value == "D2" for value in industry_levels_mapping.values()):
        #     d2_question = await d2_industry_question_task
        #     if d2_question:
        #         return {"question": d2_question}
        #     else:
        #         return {"question": ""}

    return {"question": ""}


async def generate_reply_agent(
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
    """

    follow_up_system_second_string = ""

    if demoBlocked:
        from app.utils.fastmode.prompts_no_demo import (
            AMBIGUITY_FOLLOW_UP_SYSTEM,
            AMBIGUITY_CLEAR_PROMPT_SYSTEM,
        )
    else:
        from app.utils.fastmode.prompts import (
            AMBIGUITY_FOLLOW_UP_SYSTEM,
            AMBIGUITY_CLEAR_PROMPT_SYSTEM,
        )

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
            if "Industry" in questions and "Pure Play" not in questions:
                CONDITIONAL_INDSTRUCTIONS_STRING += Industry_Breakdown_Prompt
            elif "Pure Play" in questions and "Industry" not in questions:
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
        llm_async(
            messages=follow_up_messages,
            model="openai/gpt-4.1",
            extra_body={"provider": {"order": ["openai"]}},
            temperature=0.1,
        )
    )

    clear_prompt_response_task = asyncio.create_task(
        llm_async(
            messages=clear_prompt_messages,
            model="openai/gpt-4.1",
            extra_body={"provider": {"order": ["openai"]}},
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

    response = await llm_async(
        messages,
        model="meta-llama/llama-3.3-70b-instruct",
        extra_body={"provider": {"order": ["groq", "cerebras"]}},
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

    response = await llm_async(
        messages,
        model="openai/gpt-4.1",
        temperature=0.1,
        extra_body={"provider": {"order": ["openai"]}},
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


async def industry_question_guardrail_agent(context):
    messages = [
        {"role": "system", "content": INDUSTRY_QUESTION_GUARDRAIL_PROMPT},
        {"role": "user", "content": f"Here is the Conversation Context: \n\n{context}"},
    ]
    response = await llm_async(
        messages=messages,
        model="openai/gpt-oss-120b",
        extra_body={"provider": {"order": ["groq", "cerebras"]}},
        temperature=0.1,
    )

    need_to_ask_question = extract_generic(
        "<need_to_ask_question>", "</need_to_ask_question>", response
    )
    if need_to_ask_question == "0":
        return {"need_to_ask_question": False, "response": response}
    else:
        return {"need_to_ask_question": True, "response": response}


async def intent_and_target_analysis_agent(context):
    messages = [
        {"role": "system", "content": INTENT_AND_TARGET_ANALYSIS_PROMPT},
        {"role": "user", "content": f"Here is the Conversation Context: \n\n{context}"},
    ]
    response = await llm_async(
        messages=messages,
        model="openai/gpt-oss-120b",
        temperature=0.1,
        extra_body={"provider": {"order": ["groq", "cerebras"]}},
    )

    redflag = extract_generic("<category_of_case>", "</category_of_case>", response)
    if redflag:
        redflag = redflag.strip()
    if redflag == "1":
        return {"response": response, "redflag": True}
    else:
        return {"response": response, "redflag": False}


async def industry_levels_and_questions_agent(targets):
    messages = [
        {"role": "system", "content": INDUSTRY_LEVELS_AND_QUESTIONS_PROMPT},
        {
            "role": "user",
            "content": f"<Analyzed Targets and their Reasoning>{targets}</Analyzed Targets and their Reasoning>",
        },
    ]
    response = await llm_async(
        messages=messages,
        model="openai/gpt-oss-120b",
        temperature=0.1,
        extra_body={"provider": {"order": ["groq", "cerebras"]}},
    )

    need_to_ask_question = extract_generic(
        "<need_to_ask_question>", "</need_to_ask_question>", response
    )

    returned_question = ""
    if need_to_ask_question:
        need_to_ask_question = need_to_ask_question.strip()
        if need_to_ask_question == "1":
            question = extract_generic("<question>", "</question>", response)
            if question and isinstance(question, str):
                returned_question = question.strip()

    return {"question": returned_question}


async def pureplay_question_agent(targets):
    messages = [
        {"role": "system", "content": PURE_PLAY_QUESTION},
        {
            "role": "user",
            "content": f"<Analyzed Targets and their Reasoning>{targets}</Analyzed Targets and their Reasoning>",
        },
    ]
    response = await llm_async(
        messages=messages,
        model="openai/gpt-oss-120b",
        temperature=0.1,
        extra_body={"provider": {"order": ["groq", "cerebras"]}},
    )

    final_response = ""
    try:
        if "<verdict>" in response:
            verdict_score = extract_generic("<verdict>", "</verdict>", response)
            if verdict_score:
                verdict_score = verdict_score.split("~")
                if len(verdict_score) == 2:
                    verdict = verdict_score[0]
                    score = verdict_score[1]

                    if "true" in verdict.lower():
                        if int(score) > 7:
                            final_response = extract_generic(
                                "<question>", "</question>", response
                            )
                            if final_response and isinstance(final_response, str):
                                final_response = final_response.strip()
    except:
        final_response = ""

    return {"response": response, "question": final_response}


async def ai_search_questions_agent(context, clarification):

    targets_task = asyncio.create_task(intent_and_target_analysis_agent(context))
    if clarification:
        guardrails_response = await industry_question_guardrail_agent(context)
        need_to_ask_question = guardrails_response["need_to_ask_question"]
    else:
        need_to_ask_question = True
        guardrails_response = ""

    question_string = ""
    if not need_to_ask_question:
        return {"question": ""}
    targets = await targets_task
    redflag = targets["redflag"]
    if redflag:
        return {"question": ""}

    industry_question_task = asyncio.create_task(
        industry_levels_and_questions_agent(targets["response"])
    )
    pureplay_question_response = await new_pureplay_question_agent(targets["response"])
    industry_question_response = await industry_question_task

    return {
        "question": 1,
        "pureplay_question": pureplay_question_response["question"],
        "industry_question": industry_question_response["question"],
    }


async def recruitment_query_guardrails_agent(context, clarification=False):
    messages = [
        {"role": "system", "content": RECRUITMENT_QUERY_GUARDRAIL_PROMPT},
        {"role": "user", "content": f"Here is the Conversation Context: \n\n{context}"},
    ]
    response = await llm_async(
        messages=messages,
        model="openai/gpt-oss-120b",
        temperature=0.1,
        extra_body={"provider": {"order": ["groq", "cerebras"]}},
    )
    need_to_ask_question = extract_generic(
        "<need_to_ask_question>", "</need_to_ask_question>", response
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
    response = await llm_async(
        messages=messages,
        model="openai/gpt-oss-120b",
        temperature=0.1,
        extra_body={"provider": {"order": ["groq", "cerebras"]}},
    )

    return_json = {}

    criteria_map = {
        "Titles": "title",
        "Target Industries": "industry",
        "Ownership of the Target Companies": "ownership",
        "Size/Revenue of the Target Companies": "size",
        "Target Location": "location",
    }
    try:
        output_json = extract_generic("<output_json>", "</output_json>", response)
        output_json = json.loads(output_json)
        if isinstance(output_json, dict):
            # logic to correctly map questions:
            for item in output_json["missing_information"]:
                return_json[criteria_map[item["criterion"]]] = item["question"]

    except Exception as e:
        print(e)

    return return_json


async def get_recruitment_query_questions(context, clarification):
    question_generation_task = asyncio.create_task(
        recruitement_query_questions_agent(context)
    )
    guardrails_response = await recruitment_query_guardrails_agent(
        context, clarification
    )

    return_json = {}

    if guardrails_response.get("need_to_ask_question", ""):
        return_json = await question_generation_task
        return_json["recruitment_question"] = 1
    else:
        return_json["recruitment_question"] = 0

    return return_json


async def pureplay_generator(target_industry):
    messages = [
        {"role": "system", "content": PUREPLAY_GENERATOR_SYSTEM},
        {"role": "user", "content": f"Here is the target industry: {target_industry}"},
    ]
    response = await llm_async(
        messages=messages,
        model="openai/gpt-oss-120b",
        temperature=0.1,
        extra_body={"provider": {"order": ["groq", "cerebras"]}},
    )
    companies_list = extract_generic("<companies_list>", "</companies_list>", response)
    return {"response": response, "companies_list": companies_list}


async def pureplay_verdict_and_question_agent(user_query, company_list):
    messages = [
        {"role": "system", "content": PUREPLAY_VERDICT_AND_QUESTION_SYSTEM},
        {
            "role": "user",
            "content": f"<user_query>{user_query}</user_query>\n<companies_list>{company_list}</companies_list>",
        },
    ]
    response = await llm_async(
        messages=messages,
        model="openai/gpt-oss-120b",
        temperature=0.1,
        extra_body={"provider": {"order": ["groq", "cerebras"]}},
    )
    verdict = extract_generic("<verdict>", "</verdict>", response)
    question = extract_generic("<question>", "</question>", response)
    if question:
        question = question.strip()
    return {"response": response, "verdict": verdict, "question": question}


async def new_pureplay_question_agent(targets_coro):
    targets = await targets_coro
    if targets is None:
        return {"pureplay_question": "", "question": 0}

    companies_list = await pureplay_generator(targets)
    pureplay_verdict_and_question_response = await pureplay_verdict_and_question_agent(
        targets, companies_list.get("companies_list", "")
    )

    question = ""

    if pureplay_verdict_and_question_response.get("question", ""):
        question = pureplay_verdict_and_question_response.get("question", "")

    return {"pureplay_question": question, "question": 1}


async def pre_questions_coro(context, clarification):
    targets_task = asyncio.create_task(intent_and_target_analysis_agent(context))
    if clarification:
        guardrails_response = await industry_question_guardrail_agent(context)
        need_to_ask_question = guardrails_response["need_to_ask_question"]
    else:
        need_to_ask_question = True
        guardrails_response = ""

    if not need_to_ask_question:
        return None
    targets = await targets_task
    redflag = targets["redflag"]
    if redflag:
        return None

    return targets


async def new_industry_question_agent(targets_coro):
    targets = await targets_coro
    if targets is None:
        return {"industry_question": "", "question": 0}

    returned_question = ""

    industry_question_response = await industry_levels_and_questions_agent(
        targets["response"]
    )

    if industry_question_response.get("question", ""):
        returned_question = industry_question_response.get("question", "")

    return {"industry_question": returned_question, "question": 1}
