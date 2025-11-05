import re
import json
from qutils.llm.asynchronous import invoke, stream

from app.utils.outreach.services.chat_services.prompts import (
    CHAT_AGENT_SYSTEM_PROMPT,
    CAMPAIGN_CHAT_AGENT_SYSTEM_PROMPT,
    ROUNDS_DECIDER_PROMPT,
    MODIFY_MESSAGE_PROMPT,
    MASTER_CAMPAIGN_AGENT_SYSTEM_PROMPT,
    CANDIDATE_ROUNDS_DECIDER_PROMPT,
)
from copy import deepcopy
from app.core.database import postgres_fetch, postgres_insert
from typing import List
from app.utils.outreach.utils.summary_generation.generate_summary import (
    generate_summary,
)
from elasticsearch import AsyncElasticsearch
import os
import asyncio


async def req_validator(message, context=None):

    system_prompt = """
    You are a highly accurate user message validator. 
    """

    prompt = f"Validate the following user: {message}."
    if context:
        prompt += f"The Previous Context: {context}."

    response = await invoke(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        model="openai/gpt-4.1-nano",
        temperature=0,
        max_tokens=512,
        verbose=False,
    )

    return response.strip()


async def get_profile(
    profile_id: str,
    client: AsyncElasticsearch,
    search_term: str = "_id",
):

    results = await client.search(
        body={
            "query": {"term": {search_term: profile_id}},
        },
        index=os.getenv("ES_PROFILES_INDEX"),
        size=1,
    )

    try:
        if not results["hits"]["hits"]:
            return {
                "profileData": {"_source": {}},
            }

        es_result = results["hits"]["hits"][0]
        source_data = es_result.get("_source", {})
        # Map fields to match desired output format
        mapped_source = {
            "id": source_data.get("_id", es_result.get("_id")),
            "firstName": source_data.get("first_name", ""),
            "lastName": source_data.get("last_name", ""),
            "fullName": source_data.get("full_name", ""),
            "urn": source_data.get("entity_urn", ""),
            "publicIdentifier": source_data.get("public_identifier", ""),
            "headline": source_data.get("headline", ""),
            "summary": source_data.get("summary", ""),
            "skills": source_data.get("skills", []),
            "updatedAt": source_data.get("updated_at", ""),
            "location": source_data.get("location", ""),
            "experience": source_data.get("experience", []),
            "education": source_data.get("education", []),
            "imageUrl": source_data.get("image_url", ""),
            "_id": es_result.get("_id"),
        }
        data = await generate_summary(profileData=mapped_source, sample_flag=True)
        return data

    except Exception as e:
        raise e


def extract_generic(start: str, end: str, text: str):
    """
    Extracts text between two specified delimiters using regular expressions.

    This function searches for text that appears between the start and end delimiters
    in the provided text string, handling multi-line content with the DOTALL flag.

    Args:
        start (str): The starting delimiter to search for
        end (str): The ending delimiter to search for
        text (str): The text to search within

    Returns:
        str or None: The extracted text if found, None otherwise
    """
    match = re.search(rf"{start}(.*?){end}", text, re.DOTALL)
    return match.group(1) if match else None


async def identify_rounds(rounds_queries: List[str], rounds):
    system_prompt = deepcopy(ROUNDS_DECIDER_PROMPT)
    tasks = []
    for i in range(len(rounds_queries)):
        user_prompt = f"""<rounds> {json.dumps(rounds)} </rounds>\n<query> {rounds_queries[i]} </query>"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        tasks.append(
            invoke(messages=messages, model="openai/gpt-4.1-mini", temperature=0.1)
        )
    result = await asyncio.gather(*tasks)

    round_ids = []

    for res in result:
        round_id = extract_generic("<desired_rounds>", "</desired_rounds>", res)
        round_id = eval(round_id)
        round_ids.append(round_id)

    print(f"round_ids: {round_ids}")

    return round_ids


async def modify_message(message, query, channel, subject="", profile_summary=""):
    # print("modifying message")

    system_prompt = deepcopy(MODIFY_MESSAGE_PROMPT)
    character_limit = "None"
    if channel == "linkedin_connect":
        character_limit = 200
    elif channel == "linkedin_premium":
        character_limit = 300
    if subject:
        user_prompt = f"""<message> {message} </message>\n<profile_summary> {profile_summary} </profile_summary>\n<query> {query} </query>\n<channel> {channel} </channel>\n<subject> {subject} </subject>\n<character_limit> {character_limit} </character_limit>"""
    else:
        user_prompt = f"""<message> {message} </message>\n<profile_summary> {profile_summary} </profile_summary>\n<query> {query} </query>\n<channel> {channel} </channel>\n<character_limit> {character_limit} </character_limit>"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    result = await invoke(
        messages=messages, model="openai/gpt-4.1-mini", temperature=0.1
    )

    modified_message = extract_generic(
        "<modified_message>", "</modified_message>", result
    )
    message_for_user = extract_generic(
        "<message_for_user>", "</message_for_user>", result
    )
    modified_subject = extract_generic(
        "<modified_subject>", "</modified_subject>", result
    )
    return modified_message, message_for_user, modified_subject


async def converse_chat_agent(
    message, conv_id, sender_name, campaign_profiles, es_client
):
    """Handle conversations for sample_message_agent"""
    system_prompt = CHAT_AGENT_SYSTEM_PROMPT
    current_response_id = 1

    if campaign_profiles:
        context = ""
        if es_client:
            campaign_profiles = await get_profile(campaign_profiles[0], es_client)
            print(campaign_profiles)
        else:
            campaign_profiles = "Not Available"
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"<user_name>This is the person that is reaching out: {sender_name}. You are writing on their behalf basically.</user_name>\n<sample_profile_summary>This is who you are reaching out to: {campaign_profiles}</sample_profile_summary>\n<message>{message}</message>",
            },
        ]
    else:
        context = await postgres_fetch(
            f"SELECT sample_message_agent_messages FROM outreach_converse WHERE conv_id = '{conv_id}'"
        )
        if context:
            message1 = f"<user_name>This is the person that is reaching out: {sender_name}. You are writing on their behalf basically.</user_name>\n<sample_profile_summary>This is who you are reaching out to: {context[0][0]}</sample_profile_summary>\n<message>{message}</message>"
            messages = context[0][1:] + [{"role": "user", "content": message1}]
        else:
            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"<user_name>{sender_name}</user_name>\n<message>{message}</message>",
                },
            ]

    buffer = ""
    sample_inside_sample = False
    sample_message_found = False
    show_profile_yielded = False

    inside_context_section = False
    sample_open_tag = "<sample_message>"
    sample_close_tag = "</sample_message>"
    context_open_tag = "<context_summary>"
    context_close_tag = "</context_summary>"
    assistant_message = ""
    context_section_buffer = ""

    try:
        async for chunk in stream(
            messages=messages, model="openai/gpt-4.1", temperature=0.2
        ):
            buffer += chunk
            assistant_message += chunk

            while True:
                if inside_context_section:
                    context_section_buffer += buffer
                    buffer = ""

                    if context_close_tag in context_section_buffer:
                        context_content = extract_generic(
                            context_open_tag, context_close_tag, context_section_buffer
                        )
                        if context_content:
                            yield {
                                "step": "transition",
                                "text": context_content,
                                "agent_type": "sample_campaign_agent",
                            }

                        close_idx = context_section_buffer.rfind(
                            context_close_tag
                        ) + len(context_close_tag)

                        buffer = context_section_buffer[close_idx:]
                        context_section_buffer = ""
                        inside_context_section = False
                        continue
                    else:
                        break

                elif sample_inside_sample:
                    end_idx = buffer.find(sample_close_tag)
                    if end_idx == -1:
                        safe_end = len(buffer) - len(sample_close_tag) + 1
                        if safe_end > 0:
                            data = buffer[:safe_end]
                            yield {
                                "step": "sample_message",
                                "text": data,
                                "response_id": 3,
                            }
                            buffer = buffer[safe_end:]
                            sample_message_found = True

                        break
                    else:
                        if end_idx > 0:
                            data = buffer[:end_idx]
                            yield {
                                "step": "sample_message",
                                "text": data,
                                "response_id": 3,
                            }
                            sample_message_found = True
                        buffer = buffer[end_idx + len(sample_close_tag) :]
                        sample_inside_sample = False
                        current_response_id = 4  # Next normal text gets response_id 4

                else:
                    context_start_idx = buffer.find(context_open_tag)
                    sample_start_idx = buffer.find(sample_open_tag)

                    next_tag_idx = -1
                    is_context_tag = False

                    if context_start_idx != -1 and sample_start_idx != -1:
                        if context_start_idx < sample_start_idx:
                            next_tag_idx = context_start_idx
                            is_context_tag = True
                        else:
                            next_tag_idx = sample_start_idx
                            is_context_tag = False
                    elif context_start_idx != -1:
                        next_tag_idx = context_start_idx
                        is_context_tag = True
                    elif sample_start_idx != -1:
                        next_tag_idx = sample_start_idx
                        is_context_tag = False

                    if next_tag_idx == -1:
                        max_tag_length = max(
                            len(context_open_tag), len(sample_open_tag)
                        )
                        safe_end = len(buffer) - max_tag_length + 1
                        if safe_end > 0:
                            data = buffer[:safe_end]

                            # Check if we have a partial sample_message tag and yield show_profile if not already done
                            if not show_profile_yielded:
                                remaining_buffer = buffer[safe_end:]
                                # Check if remaining buffer is a partial match for sample_open_tag
                                if remaining_buffer and sample_open_tag.startswith(
                                    remaining_buffer
                                ):
                                    yield {
                                        "step": "show_profile",
                                        "text": "",
                                        "response_id": 2,
                                    }
                                    show_profile_yielded = True

                            yield {
                                "step": "text_line",
                                "text": data,
                                "response_id": current_response_id,
                            }
                            buffer = buffer[safe_end:]
                        break
                    else:
                        if next_tag_idx > 0:
                            data = buffer[:next_tag_idx]
                            yield {
                                "step": "text_line",
                                "text": data,
                                "response_id": current_response_id,
                            }

                        if is_context_tag:
                            context_section_buffer = buffer[next_tag_idx:]
                            buffer = ""
                            inside_context_section = True
                        else:
                            # Yield show_profile event when sample_message tag is first detected
                            if not show_profile_yielded:
                                yield {
                                    "step": "show_profile",
                                    "text": "",
                                    "response_id": 2,
                                }
                                show_profile_yielded = True

                            buffer = buffer[next_tag_idx + len(sample_open_tag) :]
                            sample_inside_sample = True

        if buffer:
            if inside_context_section:
                context_section_buffer += buffer
                if context_close_tag in context_section_buffer:
                    context_content = extract_generic(
                        context_open_tag, context_close_tag, context_section_buffer
                    )
                    if context_content:
                        yield {
                            "step": "transition",
                            "text": context_content,
                            "agent_type": "sample_campaign_agent",
                        }
            else:
                data = buffer
                yield {
                    "step": "sample_message" if sample_inside_sample else "text_line",
                    "text": data,
                    "response_id": 3 if sample_inside_sample else current_response_id,
                }
        if sample_message_found:
            yield {
                "step": "generate_for_all_rounds",
                "text": "",
                "response_id": 5,
            }

    finally:
        messages.append({"role": "assistant", "content": assistant_message})

        if campaign_profiles:
            messages = [
                {"role": "campaign_profile", "content": str(campaign_profiles)}
            ] + messages

        json_messages = json.dumps(messages)
        json_messages = json_messages.replace("'", "''")
        if context:
            await postgres_insert(
                f"UPDATE outreach_converse SET sample_message_agent_messages = '{json_messages}' WHERE conv_id = '{conv_id}'"
            )
        else:
            rows = await postgres_fetch(
                f"SELECT 1 FROM outreach_converse WHERE conv_id = '{conv_id}'"
            )
            if not rows:
                await postgres_insert(
                    f"INSERT INTO outreach_converse (conv_id, sample_message_agent_messages, sample_campaign_agent_messages) VALUES ('{conv_id}', '{json_messages}', NULL)"
                )
            else:
                await postgres_insert(
                    f"UPDATE outreach_converse SET sample_message_agent_messages = '{json_messages}' WHERE conv_id = '{conv_id}'"
                )


async def converse_unified_campaign_agent(
    message,
    conv_id,
    sender_name,
    rounds,
    round_messages,
    context_summary,
    es_client,
    campaign_profiles=None,  # None for campaign agent, dict for master agent
    master=False,
):

    is_master_mode = master

    if is_master_mode:
        system_prompt = deepcopy(MASTER_CAMPAIGN_AGENT_SYSTEM_PROMPT)
        db_field = "sample_campaign_agent_messages"
    else:
        system_prompt = deepcopy(CAMPAIGN_CHAT_AGENT_SYSTEM_PROMPT)
        db_field = "sample_campaign_agent_messages"

    print("Master Mode: ", is_master_mode)
    print(f"campaign_profiles: {campaign_profiles}")

    system_prompt += f"\n<summary_by_sample_message_agent>{context_summary}</summary_by_sample_message_agent>"
    current_response_id = 1

    context = None
    if not is_master_mode:
        # Get conversation context
        context = await postgres_fetch(
            f"SELECT {db_field} FROM outreach_converse WHERE conv_id = '{conv_id}'"
        )
        if context and context[0]:
            messages = context[0] + [{"role": "user", "content": message}]
        else:
            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"<user_name>{sender_name}</user_name>\n<message>{message}</message>",
                },
            ]
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"<user_name>{sender_name}</user_name>\n<message>{message}</message>",
            },
        ]

    buffer = ""
    inside_modify_section = False
    inside_context_section = False

    modify_open_tag = "<modify_query>"
    modify_close_tag = "</modify_query>"
    message_query_open_tag = "<message_query>"
    message_query_close_tag = "</message_query>"
    context_open_tag = "<context_summary>"
    context_close_tag = "</context_summary>"

    # Master-specific tag
    publish_tag = "<publish_campaign>"

    assistant_message = ""
    modify_section_buffer = ""
    context_section_buffer = ""

    try:
        async for chunk in stream(
            messages=messages, model="openai/gpt-4.1", temperature=0.2
        ):
            buffer += chunk
            assistant_message += chunk

            # Check for publish tag (master mode only)
            if is_master_mode and publish_tag in buffer:
                publish_idx = buffer.find(publish_tag)
                if publish_idx >= 0:
                    if publish_idx > 0:
                        data = buffer[:publish_idx]
                        yield {
                            "step": "text_line",
                            "text": data,
                            "response_id": current_response_id,
                        }
                    yield {
                        "step": "publish",
                        "text": "",
                        "response_id": current_response_id + 1,
                    }
                    buffer = buffer[publish_idx + len(publish_tag) :]
                    continue

            while True:
                if inside_context_section:
                    context_section_buffer += buffer
                    buffer = ""

                    if context_close_tag in context_section_buffer:
                        context_content = extract_generic(
                            context_open_tag, context_close_tag, context_section_buffer
                        )
                        if context_content:
                            next_agent = "campaign_master_agent"
                            yield {
                                "step": "transition",
                                "text": context_content,
                                "agent_type": next_agent,
                            }

                        close_idx = context_section_buffer.rfind(
                            context_close_tag
                        ) + len(context_close_tag)
                        buffer = context_section_buffer[close_idx:]
                        context_section_buffer = ""
                        inside_context_section = False
                        continue
                    else:
                        break

                elif inside_modify_section:
                    modify_section_buffer += buffer
                    buffer = ""

                    # Check required closing tags based on mode
                    required_tags = [modify_close_tag, message_query_close_tag]
                    all_tags_present = all(
                        tag in modify_section_buffer for tag in required_tags
                    )

                    if all_tags_present:
                        try:
                            modify_queries_str = extract_generic(
                                modify_open_tag, modify_close_tag, modify_section_buffer
                            )
                            message_queries_str = extract_generic(
                                message_query_open_tag,
                                message_query_close_tag,
                                modify_section_buffer,
                            )

                            if modify_queries_str and message_queries_str:
                                modify_queries = eval(modify_queries_str)
                                message_queries = eval(message_queries_str)

                                yield {
                                    "step": "modifying_message",
                                    "text": "",
                                    "response_id": current_response_id + 1,
                                }

                                identified_rounds = await identify_rounds(
                                    message_queries, rounds
                                )
                                modify_tasks = []
                                for i, round_ids in enumerate(identified_rounds):
                                    if i < len(modify_queries):
                                        query = modify_queries[i]

                                        if is_master_mode:
                                            for round_id in round_ids:
                                                if round_id in round_messages:
                                                    round_data = round_messages[
                                                        round_id
                                                    ]
                                                    message_content = round_data.get(
                                                        "message", ""
                                                    )
                                                    subject_content = round_data.get(
                                                        "subject", ""
                                                    )
                                                    channel = rounds.get(round_id, "")

                                                    profile_summary = ""
                                                    candidate_id = ""
                                                    (
                                                        candidate_id,
                                                        selected_candidate_data,
                                                    ) = next(
                                                        iter(campaign_profiles.items())
                                                    )
                                                    if isinstance(
                                                        selected_candidate_data, dict
                                                    ):
                                                        es_id = (
                                                            selected_candidate_data.get(
                                                                "es_id", ""
                                                            )
                                                        )
                                                        profile_summary = (
                                                            await get_profile(
                                                                es_id, es_client
                                                            )
                                                        )

                                                    modify_tasks.append(
                                                        {
                                                            "task": modify_message(
                                                                message_content,
                                                                query,
                                                                channel,
                                                                subject_content,
                                                                profile_summary,
                                                            ),
                                                            "round_id": round_id,
                                                            "candidate_id": candidate_id,
                                                        }
                                                    )
                                        else:
                                            for round_id in round_ids:
                                                if round_id in round_messages:
                                                    round_data = round_messages[
                                                        round_id
                                                    ]
                                                    message_content = round_data.get(
                                                        "message", ""
                                                    )
                                                    subject_content = round_data.get(
                                                        "subject", ""
                                                    )
                                                    channel = rounds.get(round_id, "")

                                                    modify_tasks.append(
                                                        {
                                                            "task": modify_message(
                                                                message_content,
                                                                query,
                                                                channel,
                                                                subject_content,
                                                            ),
                                                            "round_id": round_id,
                                                            "candidate_id": None,
                                                        }
                                                    )

                                    if modify_tasks:
                                        task_results = await asyncio.gather(
                                            *[task["task"] for task in modify_tasks]
                                        )
                                        print(task_results)

                                        yield_generate = False
                                        for i, (
                                            modified_message,
                                            message_for_user,
                                            modified_subject,
                                        ) in enumerate(task_results):
                                            round_id = modify_tasks[i]["round_id"]
                                            candidate_id = modify_tasks[i][
                                                "candidate_id"
                                            ]

                                            modified_data = {}
                                            if modified_message:
                                                modified_data["message"] = (
                                                    modified_message
                                                )
                                            if modified_subject:
                                                modified_data["subject"] = (
                                                    modified_subject
                                                )

                                            if modified_data:
                                                if is_master_mode:
                                                    # Master mode: {candidate_id: {round_id: data}}
                                                    yield {
                                                        "step": "modified_message",
                                                        "data": {
                                                            candidate_id: {
                                                                round_id: modified_data
                                                            }
                                                        },
                                                        "response_id": current_response_id
                                                        + 2,
                                                    }
                                                else:
                                                    # Campaign mode: {round_id: data}
                                                    yield {
                                                        "step": "modified_message",
                                                        "data": {
                                                            round_id: modified_data
                                                        },
                                                        "response_id": current_response_id
                                                        + 2,
                                                    }
                                                yield_generate = True

                                        for (
                                            modified_message,
                                            message_for_user,
                                            modified_subject,
                                        ) in task_results:
                                            if message_for_user:
                                                yield {
                                                    "step": "text_line",
                                                    "text": message_for_user,
                                                    "response_id": current_response_id
                                                    + 3,
                                                }

                                        if yield_generate and not is_master_mode:
                                            yield {
                                                "step": "generate_for_all_profiles",
                                                "text": "",
                                                "response_id": current_response_id + 4,
                                            }

                        except Exception as e:
                            print(f"Error processing modify section: {e}")

                        # Find end of section and continue
                        close_indices = [
                            modify_section_buffer.rfind(tag) + len(tag)
                            for tag in required_tags
                        ]
                        last_close_idx = max(close_indices)

                        buffer = modify_section_buffer[last_close_idx:]
                        modify_section_buffer = ""
                        inside_modify_section = False
                        continue
                    else:
                        break

                else:
                    # Look for opening tags
                    context_start_idx = buffer.find(context_open_tag)
                    modify_start_idx = buffer.find(modify_open_tag)

                    # Determine which tag comes first
                    next_tag_idx = -1
                    is_context_tag = False

                    if context_start_idx != -1 and modify_start_idx != -1:
                        if context_start_idx < modify_start_idx:
                            next_tag_idx = context_start_idx
                            is_context_tag = True
                        else:
                            next_tag_idx = modify_start_idx
                    elif context_start_idx != -1:
                        next_tag_idx = context_start_idx
                        is_context_tag = True
                    elif modify_start_idx != -1:
                        next_tag_idx = modify_start_idx

                    if next_tag_idx == -1:
                        # No tags found, yield safely
                        max_tag_length = max(
                            len(context_open_tag), len(modify_open_tag)
                        )
                        safe_end = len(buffer) - max_tag_length + 1
                        if safe_end > 0:
                            data = buffer[:safe_end]

                            yield {
                                "step": "text_line",
                                "text": data,
                                "response_id": current_response_id,
                            }
                            buffer = buffer[safe_end:]
                        break
                    else:
                        # Found a tag
                        if next_tag_idx > 0:
                            data = buffer[:next_tag_idx]

                            yield {
                                "step": "text_line",
                                "text": data,
                                "response_id": current_response_id,
                            }

                        if is_context_tag:
                            context_section_buffer = buffer[next_tag_idx:]
                            buffer = ""
                            inside_context_section = True
                        else:
                            modify_section_buffer = buffer[next_tag_idx:]
                            buffer = ""
                            inside_modify_section = True

        # Handle remaining buffer
        if buffer:
            if inside_context_section:
                context_section_buffer += buffer
                if context_close_tag in context_section_buffer:
                    context_content = extract_generic(
                        context_open_tag, context_close_tag, context_section_buffer
                    )
                    if context_content:
                        next_agent = "campaign_master_agent"
                        yield {
                            "step": "transition",
                            "text": context_content,
                            "agent_type": next_agent,
                        }
            elif not inside_modify_section:
                yield {
                    "step": "text_line",
                    "text": buffer,
                    "response_id": current_response_id,
                }

    finally:
        # Save conversation state
        messages.append({"role": "assistant", "content": assistant_message})
        json_messages = json.dumps(messages)
        json_messages = json_messages.replace("'", "''")

        await postgres_insert(
            f"UPDATE outreach_converse SET {db_field} = '{json_messages}' WHERE conv_id = '{conv_id}'"
        )


async def cache_campaign_profiles(conv_id, profiles, es_client):
    profile_map = {
        f"candidate_{i+1}": {"_id": profile, "headline": ""}
        for i, profile in enumerate(profiles)
    }
    profiles = await get_profile(profiles, es_client)
    for k, v in profiles.items():
        profile_map[k]["headline"] = v
    json_profiles = json.dumps(profile_map)
    json_profiles = json_profiles.replace("'", "''")
    await postgres_insert(
        f"INSERT INTO outreach_campaign_profiles (conv_id, profiles) VALUES ('{conv_id}', '{json_profiles}')"
    )


async def converse(
    message,
    conv_id,
    sender_name=None,
    campaign_profiles=[],
    es_client=None,
    rounds={},
    agent_type="sample_message_agent",
    round_messages={},
    context_summary="",
    selected_profile={},
):
    if campaign_profiles:
        # asyncio.create_task(
        #     cache_campaign_profiles(conv_id, campaign_profiles, es_client)
        # )
        pass
    if agent_type == "sample_message_agent":
        async for result in converse_chat_agent(
            message, conv_id, sender_name, campaign_profiles, es_client
        ):
            yield {"event": result}
    else:
        if agent_type == "campaign_master_agent":
            campaign_profiles = selected_profile
            master = True
        else:
            campaign_profiles = None
            master = False

        async for result in converse_unified_campaign_agent(
            message,
            conv_id,
            sender_name,
            rounds,
            round_messages,
            context_summary,
            es_client,
            campaign_profiles,
            master,
        ):
            yield {"event": result}


# async def get_profile(
#     search_ids: List[str],
#     client: AsyncElasticsearch,
#     search_term: str = "_id",
#     additional_source: List[str] = [],
#     return_list: bool = True,
# ) -> List:
#     data_map = {}
#     data_lst = []
#     results = await client.search(
#         body={
#             "_source": [
#                 "headline",
#                 "experience",
#             ],
#             "query": {"terms": {search_term: search_ids}},
#         },
#         index=os.getenv("ES_PROFILES_INDEX"),
#         size=len(search_ids),
#     )
#     try:
#         for es_result in results["hits"]["hits"]:
#             profile = es_result.get("_source", [])
#             if profile:
#                 headline = profile.get("headline", "")
#                 if not headline:
#                     experience = profile.get("experience", [])
#                     if experience:
#                         headline = experience[0].get("profile_headline", "")
#                     if not headline:
#                         headline = experience[0].get("title", "")
#             data_map[es_result.get("_id")] = headline
#             data_lst.append(headline)
#         # data = {k: v for k, v in data_map.items() if v}
#     except Exception as e:
#         raise e
#     return data_lst if return_list else data_map

# async def converse_campaign_agent(
#     message, conv_id, sender_name, rounds, round_messages, context_summary, campaign_profiles = {}
# ):

#     is_master_mode = campaign_profiles is not None

#     if is_master_mode:
#         system_prompt = deepcopy(MASTER_CAMPAIGN_AGENT_SYSTEM_PROMPT)
#     else:
#         system_prompt = deepcopy(CAMPAIGN_CHAT_AGENT_SYSTEM_PROMPT)

#     system_prompt += f"\n<summary_by_sample_message_agent>{context_summary}</summary_by_sample_message_agent>"
#     current_response_id = 1

#     # Get conversation context
#     context = await postgres_fetch(
#         f"SELECT sample_campaign_agent_messages FROM outreach_converse WHERE conv_id = '{conv_id}'"
#     )
#     if context and context[0]:
#         messages = context[0] + [{"role": "user", "content": message}]
#     else:
#         messages = [
#             {"role": "system", "content": system_prompt},
#             {
#                 "role": "user",
#                 "content": f"<user_name>{sender_name}</user_name>\n<message>{message}</message>",
#             },
#         ]

#     buffer = ""
#     yield_generate_for_all_profiles = False
#     inside_modify_section = False
#     inside_context_section = False
#     modify_open_tag = "<modify_query>"
#     modify_close_tag = "</modify_query>"
#     message_query_open_tag = "<message_query>"
#     message_query_close_tag = "</message_query>"
#     context_open_tag = "<context_summary>"
#     context_close_tag = "</context_summary>"
#     assistant_message = ""
#     modify_section_buffer = ""
#     context_section_buffer = ""
#     candidate_query_open_tag = "<candidate_query>"
#     candidate_query_close_tag = "</candidate_query>"
#     publish_tag = "<publish_campaign>"

#     try:
#         async for chunk in stream(
#             messages=messages, model="openai/gpt-4.1", temperature=0.2
#         ):
#             buffer += chunk
#             assistant_message += chunk

#             if is_master_mode and publish_tag in buffer:
#                 publish_idx = buffer.find(publish_tag)
#                 if publish_idx >= 0:
#                     if publish_idx > 0:
#                         data = buffer[:publish_idx]
#                         yield {
#                             "step": "text_line",
#                             "text": data,
#                             "response_id": current_response_id,
#                         }
#                     yield {
#                         "step": "publish",
#                         "text": "",
#                         "response_id": current_response_id + 1,
#                     }
#                     buffer = buffer[publish_idx + len(publish_tag):]
#                     continue

#             while True:
#                 if inside_context_section:
#                     context_section_buffer += buffer
#                     buffer = ""

#                     if context_close_tag in context_section_buffer:
#                         context_content = extract_generic(
#                             context_open_tag, context_close_tag, context_section_buffer
#                         )
#                         if context_content:
#                             yield {
#                                 "step": "transition",
#                                 "text": context_content,
#                                 "agent_type": "campaign_master_agent",
#                             }

#                         close_idx = context_section_buffer.rfind(
#                             context_close_tag
#                         ) + len(context_close_tag)

#                         buffer = context_section_buffer[close_idx:]
#                         context_section_buffer = ""
#                         inside_context_section = False
#                         continue
#                     else:
#                         break

#                 elif inside_modify_section:
#                     modify_section_buffer += buffer
#                     buffer = ""

#                     print(
#                         f"DEBUG: In modify section, buffer length: {len(modify_section_buffer)}"
#                     )
#                     print(
#                         f"DEBUG: Looking for closing tags - modify_close in buffer: {modify_close_tag in modify_section_buffer}, message_query_close in buffer: {message_query_close_tag in modify_section_buffer}"
#                     )

#                     # Check if we have both closing tags
#                     if (
#                         modify_close_tag in modify_section_buffer
#                         and message_query_close_tag in modify_section_buffer
#                     ):
#                         try:
#                             print(
#                                 "DEBUG: Both closing tags found, processing modify section"
#                             )
#                             modify_queries_str = extract_generic(
#                                 modify_open_tag, modify_close_tag, modify_section_buffer
#                             )
#                             message_queries_str = extract_generic(
#                                 message_query_open_tag,
#                                 message_query_close_tag,
#                                 modify_section_buffer,
#                             )

#                             print(
#                                 f"DEBUG: Extracted modify_queries_str: {modify_queries_str}"
#                             )
#                             print(
#                                 f"DEBUG: Extracted message_queries_str: {message_queries_str}"
#                             )

#                             if modify_queries_str and message_queries_str:
#                                 modify_queries = eval(modify_queries_str)
#                                 message_queries = eval(message_queries_str)

#                                 yield {
#                                     "step": "modifying_message",
#                                     "text": "",
#                                     "response_id": current_response_id + 1,
#                                 }

#                                 identified_rounds = await identify_rounds(
#                                     message_queries, rounds
#                                 )

#                                 print(
#                                     f"identified_rounds: {identified_rounds}, message_queries: {message_queries}, modify_queries: {modify_queries}"
#                                 )

#                                 modify_tasks = []
#                                 for i, round_ids in enumerate(identified_rounds):
#                                     if i < len(modify_queries):
#                                         query = modify_queries[i]
#                                         for round_id in round_ids:
#                                             if round_id in round_messages:
#                                                 round_data = round_messages[round_id]
#                                                 message_content = round_data.get(
#                                                     "message", ""
#                                                 )
#                                                 subject_content = round_data.get(
#                                                     "subject", ""
#                                                 )

#                                                 print(
#                                                     f"message_content: {message_content}, subject_content: {subject_content}"
#                                                 )

#                                                 channel = ""
#                                                 # print(f"rounds: {rounds}")
#                                                 channel = rounds.get(round_id, "")
#                                                 # for round_info in rounds:
#                                                 #     if round_id in round_info:
#                                                 #         channel = round_info[round_id]
#                                                 #         break

#                                                 modify_tasks.append(
#                                                     {
#                                                         "task": modify_message(
#                                                             message_content,
#                                                             query,
#                                                             channel,
#                                                             subject_content,
#                                                         ),
#                                                         "round_id": round_id,
#                                                     }
#                                                 )

#                                 if modify_tasks:
#                                     task_results = await asyncio.gather(
#                                         *[task["task"] for task in modify_tasks]
#                                     )

#                                     for i, (
#                                         modified_message,
#                                         message_for_user,
#                                         modified_subject,
#                                     ) in enumerate(task_results):
#                                         round_id = modify_tasks[i]["round_id"]
#                                         modified_data = {}

#                                         if modified_message:
#                                             modified_data["message"] = modified_message
#                                         if modified_subject:
#                                             modified_data["subject"] = modified_subject

#                                         if modified_data:
#                                             yield {
#                                                 "step": "modified_message",
#                                                 "data": {round_id: modified_data},
#                                                 "response_id": current_response_id + 2,
#                                             }
#                                             yield_generate_for_all_profiles = True

#                                     for (
#                                         modified_message,
#                                         message_for_user,
#                                         modified_subject,
#                                     ) in task_results:
#                                         if message_for_user:
#                                             yield {
#                                                 "step": "text_line",
#                                                 "text": message_for_user,
#                                                 "response_id": current_response_id + 3,
#                                             }
#                                             yield_generate_for_all_profiles = True
#                                     if yield_generate_for_all_profiles:
#                                         yield {
#                                             "step": "generate_for_all_profiles",
#                                             "text": "",
#                                             "response_id": current_response_id + 4,
#                                         }
#                                         yield_generate_for_all_profiles = False

#                         except Exception as e:
#                             pass

#                         # Find the end of the last closing tag and continue with remaining content
#                         last_close_idx = max(
#                             modify_section_buffer.rfind(modify_close_tag)
#                             + len(modify_close_tag),
#                             modify_section_buffer.rfind(message_query_close_tag)
#                             + len(message_query_close_tag),
#                         )

#                         # Put remaining content back in buffer
#                         buffer = modify_section_buffer[last_close_idx:]
#                         modify_section_buffer = ""
#                         inside_modify_section = False
#                         continue
#                     else:
#                         break

#                 else:
#                     # Check for context_summary tag first, then modify tags
#                     context_start_idx = buffer.find(context_open_tag)
#                     modify_start_idx = buffer.find(modify_open_tag)

#                     # Determine which tag comes first (or if any exist)
#                     next_tag_idx = -1
#                     is_context_tag = False

#                     if context_start_idx != -1 and modify_start_idx != -1:
#                         if context_start_idx < modify_start_idx:
#                             next_tag_idx = context_start_idx
#                             is_context_tag = True
#                         else:
#                             next_tag_idx = modify_start_idx
#                             is_context_tag = False
#                     elif context_start_idx != -1:
#                         next_tag_idx = context_start_idx
#                         is_context_tag = True
#                     elif modify_start_idx != -1:
#                         next_tag_idx = modify_start_idx
#                         is_context_tag = False

#                     if next_tag_idx == -1:
#                         # No tags found, yield safely
#                         max_tag_length = max(
#                             len(context_open_tag), len(modify_open_tag)
#                         )
#                         safe_end = len(buffer) - max_tag_length + 1
#                         if safe_end > 0:
#                             data = buffer[:safe_end]
#                             yield {
#                                 "step": "text_line",
#                                 "text": data,
#                                 "response_id": current_response_id,
#                             }
#                             buffer = buffer[safe_end:]
#                         break
#                     else:
#                         # Found a tag
#                         if next_tag_idx > 0:
#                             # Yield content before the tag
#                             data = buffer[:next_tag_idx]
#                             yield {
#                                 "step": "text_line",
#                                 "text": data,
#                                 "response_id": current_response_id,
#                             }

#                         if is_context_tag:
#                             # Start collecting context section
#                             context_section_buffer = buffer[next_tag_idx:]
#                             buffer = ""
#                             inside_context_section = True
#                         else:
#                             # Start collecting modify section
#                             modify_section_buffer = buffer[next_tag_idx:]
#                             buffer = ""
#                             inside_modify_section = True

#         if buffer:
#             if inside_context_section:
#                 context_section_buffer += buffer
#                 if context_close_tag in context_section_buffer:
#                     context_content = extract_generic(
#                         context_open_tag, context_close_tag, context_section_buffer
#                     )
#                     if context_content:
#                         yield {
#                             "step": "transition",
#                             "text": context_content,
#                             "agent_type": "campaign_master_agent",
#                         }
#             elif inside_modify_section:
#                 modify_section_buffer += buffer
#                 try:
#                     if (
#                         modify_close_tag in modify_section_buffer
#                         and message_query_close_tag in modify_section_buffer
#                     ):
#                         pass
#                 except:
#                     pass
#             else:
#                 data = buffer
#                 yield {
#                     "step": "text_line",
#                     "text": data,
#                     "response_id": current_response_id,
#                 }

#     finally:
#         messages.append({"role": "assistant", "content": assistant_message})
#         json_messages = json.dumps(messages)
#         json_messages = json_messages.replace("'", "''")
#         if context:
#             await postgres_insert(
#                 f"UPDATE outreach_converse SET sample_campaign_agent_messages = '{json_messages}' WHERE conv_id = '{conv_id}'"
#             )
#         else:
#             await postgres_insert(
#                 f"INSERT INTO outreach_converse (conv_id, sample_campaign_agent_messages) VALUES ('{conv_id}', '{json_messages}')"
#             )

# async def converse_master_campaign_agent(
#     message,
#     conv_id,
#     sender_name,
#     rounds,
#     round_messages,
#     context_summary,
#     campaign_profiles,
# ):
#     """Handle conversations for master_campaign_agent"""
#     system_prompt = deepcopy(MASTER_CAMPAIGN_AGENT_SYSTEM_PROMPT)
#     system_prompt += f"\n<summary_by_sample_message_agent>{context_summary}</summary_by_sample_message_agent>"
#     current_response_id = 1

#     context = await postgres_fetch(
#         f"SELECT master_campaign_agent_messages FROM outreach_converse WHERE conv_id = '{conv_id}'"
#     )
#     if context and context[0]:
#         messages = context[0] + [{"role": "user", "content": message}]
#     else:
#         messages = [
#             {"role": "system", "content": system_prompt},
#             {
#                 "role": "user",
#                 "content": f"<user_name>{sender_name}</user_name>\n<message>{message}</message>",
#             },
#         ]

#     buffer = ""
#     inside_modify_section = False
#     modify_open_tag = "<modify_query>"
#     modify_close_tag = "</modify_query>"
#     message_query_open_tag = "<message_query>"
#     message_query_close_tag = "</message_query>"
#     publish_tag = "<publish_campaign>"
#     assistant_message = ""
#     modify_section_buffer = ""

#     try:
#         async for chunk in stream(
#             messages=messages, model="openai/gpt-4.1", temperature=0.2
#         ):
#             buffer += chunk
#             assistant_message += chunk

#             # Check for publish tag first
#             if publish_tag in buffer:
#                 publish_idx = buffer.find(publish_tag)
#                 if publish_idx >= 0:
#                     # Yield content before the publish tag
#                     if publish_idx > 0:
#                         data = buffer[:publish_idx]
#                         yield {
#                             "step": "text_line",
#                             "text": data,
#                             "response_id": current_response_id,
#                         }

#                     # Emit publish event
#                     yield {
#                         "step": "publish",
#                         "text": "",
#                         "response_id": current_response_id + 1,
#                     }

#                     # Remove the publish tag and continue
#                     buffer = buffer[publish_idx + len(publish_tag) :]
#                     continue

#             while True:
#                 if inside_modify_section:
#                     modify_section_buffer += buffer
#                     buffer = ""

#                     print(
#                         f"DEBUG: In modify section, buffer length: {len(modify_section_buffer)}"
#                     )
#                     print(
#                         f"DEBUG: Looking for closing tags - modify_close in buffer: {modify_close_tag in modify_section_buffer}, message_query_close in buffer: {message_query_close_tag in modify_section_buffer}, candidate_query_close in buffer: {candidate_query_close_tag in modify_section_buffer}"
#                     )

#                     # Check if we have all three closing tags
#                     if (
#                         modify_close_tag in modify_section_buffer
#                         and message_query_close_tag in modify_section_buffer
#                     ):
#                         try:
#                             print(
#                                 "DEBUG: All closing tags found, processing modify section"
#                             )
#                             modify_queries_str = extract_generic(
#                                 modify_open_tag, modify_close_tag, modify_section_buffer
#                             )
#                             message_queries_str = extract_generic(
#                                 message_query_open_tag,
#                                 message_query_close_tag,
#                                 modify_section_buffer,
#                             )
#                             candidate_queries_str = extract_generic(
#                                 candidate_query_open_tag,
#                                 candidate_query_close_tag,
#                                 modify_section_buffer,
#                             )

#                             print(
#                                 f"DEBUG: Extracted modify_queries_str: {modify_queries_str}"
#                             )
#                             print(
#                                 f"DEBUG: Extracted message_queries_str: {message_queries_str}"
#                             )
#                             print(
#                                 f"DEBUG: Extracted candidate_queries_str: {candidate_queries_str}"
#                             )
#                             if len(campaign_profiles) == 1:
#                                 print(f"HEREEEE", campaign_profiles)
#                                 candidate_queries_str = (
#                                     f"['{list(campaign_profiles.keys())[0]}']"
#                                 )
#                             if (
#                                 modify_queries_str
#                                 and message_queries_str
#                                 and candidate_queries_str
#                             ):
#                                 modify_queries = eval(modify_queries_str)
#                                 message_queries = eval(message_queries_str)
#                                 candidate_queries = eval(candidate_queries_str)

#                                 yield {
#                                     "step": "modifying_message",
#                                     "text": "",
#                                     "response_id": current_response_id + 1,
#                                 }

#                                 identified_rounds, identified_candidates = (
#                                     await identify_candidate_rounds(
#                                         message_queries, rounds, campaign_profiles
#                                     )
#                                 )

#                                 print(
#                                     f"identified_rounds: {identified_rounds}, identified_candidates: {identified_candidates}, message_queries: {message_queries}, modify_queries: {modify_queries}, candidate_queries: {candidate_queries}"
#                                 )

#                                 modify_tasks = []
#                                 for i, round_ids in enumerate(identified_rounds):
#                                     candidate_ids = (
#                                         identified_candidates[i]
#                                         if i < len(identified_candidates)
#                                         else []
#                                     )
#                                     print(f"HEREEEE in loop", campaign_profiles)
#                                     print(
#                                         f"round_ids: {round_ids}, candidate_ids: {candidate_ids}"
#                                     )
#                                     if i < len(modify_queries):
#                                         query = modify_queries[i]
#                                         for round_id in round_ids:
#                                             for candidate_id in candidate_ids:
#                                                 print(
#                                                     f"ROUND_ID: {round_id}, CANDIDATE_ID: {candidate_id}"
#                                                 )
#                                                 if (
#                                                     round_id in round_messages
#                                                     and candidate_id
#                                                     in campaign_profiles
#                                                 ):
#                                                     round_data = round_messages[
#                                                         round_id
#                                                     ]
#                                                     message_content = round_data.get(
#                                                         "message", ""
#                                                     )
#                                                     subject_content = round_data.get(
#                                                         "subject", ""
#                                                     )

#                                                     print(
#                                                         f"message_content: {message_content}, subject_content: {subject_content}"
#                                                     )

#                                                     channel = ""
#                                                     channel = rounds.get(round_id, "")

#                                                     modify_tasks.append(
#                                                         {
#                                                             "task": modify_message(
#                                                                 message_content,
#                                                                 query,
#                                                                 channel,
#                                                                 subject_content,
#                                                             ),
#                                                             "round_id": round_id,
#                                                             "candidate_id": candidate_id,
#                                                         }
#                                                     )

#                                 if modify_tasks:
#                                     task_results = await asyncio.gather(
#                                         *[task["task"] for task in modify_tasks]
#                                     )

#                                     for i, (
#                                         modified_message,
#                                         message_for_user,
#                                         modified_subject,
#                                     ) in enumerate(task_results):
#                                         round_id = modify_tasks[i]["round_id"]
#                                         candidate_id = modify_tasks[i]["candidate_id"]
#                                         modified_data = {}

#                                         if modified_message:
#                                             modified_data["message"] = modified_message
#                                         if modified_subject:
#                                             modified_data["subject"] = modified_subject

#                                         if modified_data:
#                                             yield {
#                                                 "step": "modified_message",
#                                                 "data": {
#                                                     candidate_id: {
#                                                         round_id: modified_data
#                                                     }
#                                                 },
#                                                 "response_id": current_response_id + 2,
#                                             }

#                                     for (
#                                         modified_message,
#                                         message_for_user,
#                                         modified_subject,
#                                     ) in task_results:
#                                         if message_for_user:
#                                             yield {
#                                                 "step": "text_line",
#                                                 "text": message_for_user,
#                                                 "response_id": current_response_id + 3,
#                                             }

#                         except Exception as e:
#                             pass

#                         # Find the end of the last closing tag and continue with remaining content
#                         last_close_idx = max(
#                             modify_section_buffer.rfind(modify_close_tag)
#                             + len(modify_close_tag),
#                             modify_section_buffer.rfind(message_query_close_tag)
#                             + len(message_query_close_tag),
#                             modify_section_buffer.rfind(candidate_query_close_tag)
#                             + len(candidate_query_close_tag),
#                         )

#                         # Put remaining content back in buffer
#                         buffer = modify_section_buffer[last_close_idx:]
#                         modify_section_buffer = ""
#                         inside_modify_section = False
#                         continue
#                     else:
#                         break

#                 else:
#                     # Check for modify tags
#                     modify_start_idx = buffer.find(modify_open_tag)

#                     if modify_start_idx == -1:
#                         # No modify tag found, yield safely
#                         safe_end = len(buffer) - len(modify_open_tag) + 1
#                         if safe_end > 0:
#                             data = buffer[:safe_end]
#                             yield {
#                                 "step": "text_line",
#                                 "text": data,
#                                 "response_id": current_response_id,
#                             }
#                             buffer = buffer[safe_end:]
#                         break
#                     else:
#                         # Found modify tag
#                         if modify_start_idx > 0:
#                             # Yield content before the tag
#                             data = buffer[:modify_start_idx]
#                             yield {
#                                 "step": "text_line",
#                                 "text": data,
#                                 "response_id": current_response_id,
#                             }

#                         # Start collecting modify section
#                         modify_section_buffer = buffer[modify_start_idx:]
#                         buffer = ""
#                         inside_modify_section = True

#         if buffer:
#             if inside_modify_section:
#                 modify_section_buffer += buffer
#                 try:
#                     if (
#                         modify_close_tag in modify_section_buffer
#                         and message_query_close_tag in modify_section_buffer
#                         and candidate_query_close_tag in modify_section_buffer
#                     ):
#                         pass
#                 except:
#                     pass
#             else:
#                 data = buffer
#                 yield {
#                     "step": "text_line",
#                     "text": data,
#                     "response_id": current_response_id,
#                 }

#     finally:
#         messages.append({"role": "assistant", "content": assistant_message})
#         json_messages = json.dumps(messages)
#         json_messages = json_messages.replace("'", "''")
#         if context:
#             await postgres_insert(
#                 f"UPDATE outreach_converse SET master_campaign_agent_messages = '{json_messages}' WHERE conv_id = '{conv_id}'"
#             )
#         else:
#             await postgres_insert(
#                 f"INSERT INTO outreach_converse (conv_id, master_campaign_agent_messages) VALUES ('{conv_id}', '{json_messages}')"
#             )

# async def identify_candidate_rounds(rounds_queries: List[str], rounds, candidates):
#     system_prompt = deepcopy(CANDIDATE_ROUNDS_DECIDER_PROMPT)
#     tasks = []
#     for i in range(len(rounds_queries)):
#         user_prompt = f"""<rounds> {json.dumps(rounds)} </rounds>\n<candidates> {json.dumps(candidates)} </candidates>\n<query> {rounds_queries[i]} </query>"""
#         messages = [
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_prompt},
#         ]
#         tasks.append(
#             invoke(messages=messages, model="openai/gpt-4.1-mini", temperature=0.1)
#         )
#     result = await asyncio.gather(*tasks)
#     round_ids = []
#     candidate_ids = []
#     for res in result:
#         round_id = extract_generic("<desired_rounds>", "</desired_rounds>", res)
#         candidate_id = extract_generic(
#             "<desired_candidates>", "</desired_candidates>", res
#         )
#         round_id = eval(round_id)
#         candidate_id = eval(candidate_id)
#         round_ids.append(round_id)
#         candidate_ids.append(candidate_id)
#     return round_ids, candidate_ids
