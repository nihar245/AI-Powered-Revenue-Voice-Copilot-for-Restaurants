"""Test if we can get TEXT output from native-audio model via Live API."""
import asyncio
from google import genai
from google.genai import types

API_KEY = "AIzaSyBSqvU6uDtHeFX5hKGUjHKcPOE69j1g-ms"
MODEL = "gemini-2.5-flash-native-audio-latest"

client = genai.Client(api_key=API_KEY)

async def test_text_only_response():
    """Can we get text output from Live API with this model?"""
    print("=== Text-only response_modalities ===")
    config = types.LiveConnectConfig(
        response_modalities=["TEXT"],
    )
    try:
        async with client.aio.live.connect(model=MODEL, config=config) as session:
            await session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part(text="Say hello")])
            )
            text = ""
            async for msg in session.receive():
                if msg.server_content and msg.server_content.model_turn:
                    for part in msg.server_content.model_turn.parts:
                        if part.text:
                            text += part.text
                if msg.server_content and msg.server_content.turn_complete:
                    break
            print(f"Text: {text}")
    except Exception as e:
        print(f"FAILED: {e}")

async def test_audio_and_text_response():
    """Can we get both audio AND text?"""
    print("\n=== AUDIO + TEXT response_modalities ===")
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO", "TEXT"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
            )
        ),
    )
    try:
        async with client.aio.live.connect(model=MODEL, config=config) as session:
            await session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part(text="Say hello")])
            )
            text = ""
            audio_bytes = 0
            async for msg in session.receive():
                if msg.server_content and msg.server_content.model_turn:
                    for part in msg.server_content.model_turn.parts:
                        if part.text:
                            text += part.text
                        if part.inline_data and part.inline_data.data:
                            audio_bytes += len(part.inline_data.data)
                if msg.server_content and msg.server_content.turn_complete:
                    break
            print(f"Text: {text}")
            print(f"Audio bytes: {audio_bytes}")
    except Exception as e:
        print(f"FAILED: {e}")

async def test_json_extraction_via_audio_model():
    """Use the model for intent extraction - send transcript, get JSON as text via audio."""
    print("\n=== Intent extraction test ===")
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(
            parts=[types.Part(text="""You are a restaurant order JSON extraction bot.
When the user speaks an order, respond by reading out the JSON.
Example: For "I want 2 chicken biryani", say:
intent type is order, item chicken biryani quantity 2
Keep it brief.""")]
        ),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
            )
        ),
    )
    async with client.aio.live.connect(model=MODEL, config=config) as session:
        await session.send_client_content(
            turns=types.Content(role="user", parts=[types.Part(text="I want 2 chicken biryani and one cold coffee")])
        )
        audio_chunks = []
        async for msg in session.receive():
            if msg.server_content and msg.server_content.model_turn:
                for part in msg.server_content.model_turn.parts:
                    if part.inline_data and part.inline_data.data:
                        audio_chunks.append(part.inline_data.data)
            if msg.server_content and msg.server_content.turn_complete:
                break
        total = sum(len(c) for c in audio_chunks)
        print(f"Got {len(audio_chunks)} chunks, {total} bytes of audio response")
    print("SUCCESS")

async def test_with_gemini_flash():
    """Also test: can we use regular gemini-2.5-flash for text via Live API?"""
    print("\n=== gemini-2.5-flash via Live API (text) ===")
    config = types.LiveConnectConfig(
        response_modalities=["TEXT"],
    )
    try:
        async with client.aio.live.connect(model="gemini-2.5-flash", config=config) as session:
            await session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part(text="Say hello in one word")])
            )
            text = ""
            async for msg in session.receive():
                if msg.server_content and msg.server_content.model_turn:
                    for part in msg.server_content.model_turn.parts:
                        if part.text:
                            text += part.text
                if msg.server_content and msg.server_content.turn_complete:
                    break
            print(f"Text: {text}")
    except Exception as e:
        print(f"FAILED: {e}")

async def main():
    await test_text_only_response()
    await test_audio_and_text_response()
    await test_json_extraction_via_audio_model()
    await test_with_gemini_flash()

if __name__ == "__main__":
    asyncio.run(main())
