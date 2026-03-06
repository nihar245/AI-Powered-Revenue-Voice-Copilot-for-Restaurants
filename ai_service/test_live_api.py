"""Quick test of Gemini Live API with native audio dialog model."""
import asyncio
from google import genai
from google.genai import types

API_KEY = "AIzaSyBSqvU6uDtHeFX5hKGUjHKcPOE69j1g-ms"
MODEL = "gemini-2.5-flash-native-audio-latest"

client = genai.Client(api_key=API_KEY)

async def test_text_to_audio():
    """Test sending text and getting audio back via Live API."""
    print("=== Text -> Audio via Live API ===")
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
            )
        ),
    )
    async with client.aio.live.connect(model=MODEL, config=config) as session:
        await session.send_client_content(
            turns=types.Content(role="user", parts=[types.Part(text="Say hello briefly")])
        )
        audio_chunks = []
        mime_type = None
        async for msg in session.receive():
            if msg.server_content and msg.server_content.model_turn:
                for part in msg.server_content.model_turn.parts:
                    if part.inline_data and part.inline_data.data:
                        audio_chunks.append(part.inline_data.data)
                        if mime_type is None:
                            mime_type = part.inline_data.mime_type
                            print(f"  Audio mime: {mime_type}")
            if msg.server_content and msg.server_content.turn_complete:
                break
        total_bytes = sum(len(c) for c in audio_chunks)
        print(f"Got {len(audio_chunks)} audio chunks, total {total_bytes} bytes")
    print("SUCCESS\n")

async def test_text_to_audio_with_system():
    """Test with system instruction for restaurant context."""
    print("=== Text -> Audio with system instruction ===")
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(
            parts=[types.Part(text="You are a restaurant order assistant. Be brief.")]
        ),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
            )
        ),
    )
    async with client.aio.live.connect(model=MODEL, config=config) as session:
        await session.send_client_content(
            turns=types.Content(role="user", parts=[types.Part(text="I want 2 chicken biryani")])
        )
        audio_chunks = []
        async for msg in session.receive():
            if msg.server_content and msg.server_content.model_turn:
                for part in msg.server_content.model_turn.parts:
                    if part.inline_data and part.inline_data.data:
                        audio_chunks.append(part.inline_data.data)
            if msg.server_content and msg.server_content.turn_complete:
                break
        total_bytes = sum(len(c) for c in audio_chunks)
        print(f"Got {len(audio_chunks)} audio chunks, total {total_bytes} bytes")
    print("SUCCESS\n")

async def test_generate_content_text():
    """Test if this model supports regular generate_content for text."""
    print("=== generate_content (text) ===")
    try:
        r = await client.aio.models.generate_content(
            model=MODEL,
            contents="Say hello",
            config=types.GenerateContentConfig(
                response_modalities=["TEXT"],
                temperature=0.3,
                max_output_tokens=100,
            ),
        )
        print(f"Response: {r.text}")
        print("SUCCESS\n")
    except Exception as e:
        print(f"FAILED: {e}\n")

async def main():
    await test_text_to_audio()
    await test_text_to_audio_with_system()
    await test_generate_content_text()

if __name__ == "__main__":
    asyncio.run(main())
