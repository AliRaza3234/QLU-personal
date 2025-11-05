from copy import deepcopy

from qutils.llm.asynchronous import invoke
from app.utils.dialer.services.live_pitch.live_pitch_prompts import (
    LIVE_CALL_SYSTEM_PROMPT,
    LIVE_CALL_USER_PROMPT,
)

from app.utils.dialer.utils.gpt_utils.gpt_models import GPT_MAIN_MODEL, GPT_BACKUP_MODEL


async def live_pitch_converter(pitch: str) -> str:
    """
    Asynchronously transform a voicemail pitch into a format suitable for live telephone conversations. This involves adapting the pitch to be more interactive and conversational, appropriate for a real-time dialogue scenario.

    Parameters:
        pitch (str): A string representing the voicemail pitch that needs to be converted. This pitch contains content originally crafted for voicemail, and it should be transformed to enhance engagement and make it suitable for live interaction.

    Returns:
        str: A string containing the modified pitch, tailored for live conversations. The output will include natural pauses, interactive elements, and conversational cues to facilitate a dynamic and engaging real-time dialogue.

    Functionality:
        Conversion: Transforms the provided voicemail pitch into a version suitable for live telephone conversations by adding conversational elements such as pauses and questions.

        Engagement: Enhances the pitch to encourage listener interaction and ensure that the conversation flows smoothly.

        Professionalism: Maintains the core message and professionalism of the original pitch while adapting its tone and structure for live communication.
    """

    system_prompt = deepcopy(LIVE_CALL_SYSTEM_PROMPT)
    user_prompt = deepcopy(LIVE_CALL_USER_PROMPT)

    user_prompt = user_prompt.format(text=pitch)
    chat = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    live_enhanced_text = pitch
    try:
        live_enhanced_text = await invoke(
            messages=chat, temperature=0.1, model=GPT_MAIN_MODEL
        )
    except Exception as e:
        print(
            f"live_pitch_converter primary call failed; falling back to backup model: {e}"
        )
        live_enhanced_text = await invoke(
            messages=chat, temperature=0.1, model=GPT_BACKUP_MODEL
        )

    return live_enhanced_text
