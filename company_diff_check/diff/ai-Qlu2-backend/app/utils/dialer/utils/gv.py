import os
from dotenv import load_dotenv

load_dotenv(override=True)

GPT_KEY = os.getenv("OPENAI_API_KEY")
DEEP_INFRA_KEY = os.getenv("DEEP_INFRA_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

AUDIO_CHUNK_SIZE = 400
SILENCE_AUDIO_CHUNK_SIZE = 150
