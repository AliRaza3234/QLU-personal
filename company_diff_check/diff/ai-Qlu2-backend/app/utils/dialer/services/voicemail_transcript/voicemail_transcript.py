import assemblyai as aai
import asyncio


async def transcribe_audio(audio_buffer):
    transcriber = aai.Transcriber()
    audio_bytes = bytes(audio_buffer)
    # Run the sync function in a separate thread to avoid blocking the event loop
    transcript = await asyncio.to_thread(transcriber.transcribe, audio_bytes)

    # Get duration in seconds
    # duration_seconds = transcript.audio_duration
    # print(f"Audio duration: {duration_seconds:.2f} seconds")

    return transcript.text
