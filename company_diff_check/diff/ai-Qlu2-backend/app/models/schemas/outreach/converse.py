from pydantic import BaseModel


class ConverseRequest(BaseModel):
    message: str
    conv_id: str
    sender_name: str
    campaign_profiles: list[str]
    rounds: dict = {}
    round_messages: dict = {}
    context_summary: str = ""
    agent_type: str = "sample_message_agent"
