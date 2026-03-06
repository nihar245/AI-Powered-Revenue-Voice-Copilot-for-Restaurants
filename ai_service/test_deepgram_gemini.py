"""Quick test: Deepgram STT + TTS and Gemini 2.0 Flash text."""
import asyncio
import struct
import time

DG_KEY = "762976aed83b77276c042838bf558122e26ee03f"
GEMINI_KEY = "AIzaSyBSqvU6uDtHeFX5hKGUjHKcPOE69j1g-ms"


async def test_deepgram_stt():
    from deepgram import DeepgramClient
    dg = DeepgramClient(api_key=DG_KEY)

    # Create a tiny WAV with silence
    sr, dur = 16000, 0.5
    samples = b'\x00\x00' * int(sr * dur)
    n = len(samples)
    wav = struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", 36+n, b"WAVE",
                      b"fmt ", 16, 1, 1, sr, sr*2, 2, 16, b"data", n) + samples

    print("=== DEEPGRAM STT (nova-3) ===")
    t0 = time.perf_counter()
    try:
        resp = dg.listen.v1.media.transcribe_file(
            request=wav,
            model="nova-3",
            language="en",
            smart_format=True,
        )
        elapsed = (time.perf_counter() - t0) * 1000
        transcript = resp.results.channels[0].alternatives[0].transcript
        print(f"  OK: '{transcript}' ({elapsed:.0f}ms)")
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def test_deepgram_tts():
    from deepgram import DeepgramClient
    dg = DeepgramClient(api_key=DG_KEY)

    print("\n=== DEEPGRAM TTS (aura-2-asteria-en) ===")
    t0 = time.perf_counter()
    try:
        audio_chunks = list(dg.speak.v1.audio.generate(
            text="Hello, welcome to our restaurant! What would you like to order today?",
            model="aura-2-asteria-en",
            encoding="linear16",
            container="wav",
            sample_rate=24000,
        ))
        audio_bytes = b"".join(audio_chunks)
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"  OK: {len(audio_bytes)} bytes ({elapsed:.0f}ms)")

        with open("test_dg_tts.wav", "wb") as f:
            f.write(audio_bytes)
        print(f"  Saved to test_dg_tts.wav")
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


async def test_gemini_text():
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_KEY)

    for model_name in ["gemini-2.0-flash", "gemini-2.0-flash-lite"]:
        print(f"\n=== {model_name.upper()} ===")
        t0 = time.perf_counter()
        try:
            resp = await client.aio.models.generate_content(
                model=model_name,
                contents="Reply with exactly: 'Hello, I can help you order food today!'",
                config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=50),
            )
            elapsed = (time.perf_counter() - t0) * 1000
            print(f"  OK: '{resp.text.strip()[:100]}' ({elapsed:.0f}ms)")
        except Exception as e:
            print(f"  ERROR: {e}")


async def main():
    await test_deepgram_stt()
    test_deepgram_tts()
    await test_gemini_text()
    print("\n✅ All tests done!")


if __name__ == "__main__":
    asyncio.run(main())
