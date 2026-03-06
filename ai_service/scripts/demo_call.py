"""
Demo script — simulates a voice ordering call through the pipeline.

This script demonstrates the full pipeline flow without needing
a real audio input by using TTS to generate test audio first.

Usage:
    cd ai_service
    python -m scripts.demo_call

Requirements:
    - Gemini API key configured
    - All dependencies installed (pip install -r requirements.txt)
"""

import asyncio
import json
import struct
import wave
import io
import sys
import os

# Ensure ai_service is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def create_test_audio_from_text(text: str) -> bytes:
    """
    Generate test audio by converting text to speech first.
    This simulates a customer speaking.
    """
    from app.voice.tts import synthesize_speech

    print(f"  [TTS] Generating test audio for: '{text}'")
    result = await synthesize_speech(text)
    print(f"  [TTS] Generated {len(result['audio_bytes'])} bytes in {result['duration_ms']:.0f}ms")
    return result["audio_bytes"]


def create_silent_wav(duration_sec: float = 2.0) -> bytes:
    """Create a silent WAV file as fallback test audio."""
    sample_rate = 16000
    num_samples = int(sample_rate * duration_sec)
    samples = struct.pack(f"<{num_samples}h", *([0] * num_samples))

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples)

    buf.seek(0)
    return buf.read()


async def demo_individual_endpoints():
    """Demo each pipeline step individually."""
    print("\n" + "=" * 60)
    print("  DEMO: Individual Pipeline Steps")
    print("=" * 60)

    # Step 1: Menu
    print("\n--- Step 1: Get Menu ---")
    from app.services.menu_service import get_menu_items, get_combo_rules
    menu = get_menu_items()
    print(f"  Menu items: {menu}")
    rules = get_combo_rules()
    print(f"  Combo rules: {rules}")

    # Step 2: Fuzzy Matching
    print("\n--- Step 2: Fuzzy Matching ---")
    from app.services.matching import match_items
    test_spoken = ["paner tikka", "chicken birani", "cold coffe"]
    matches = match_items(test_spoken)
    for m in matches:
        print(f"  '{m['spoken_as']}' → '{m['matched_item']}' (confidence: {m['confidence']}%)")

    # Step 3: Upsell
    print("\n--- Step 3: Upsell Suggestion ---")
    from app.services.upsell_service import suggest_upsell
    matched_names = [m["matched_item"] for m in matches if m["matched_item"]]
    upsell = suggest_upsell(matched_names)
    print(f"  Suggestion: {upsell['suggestion']}")
    print(f"  Reason: {upsell['reason']}")
    print(f"  Source: {upsell['source']}")

    # Step 4: Intent Extraction (requires Gemini API)
    print("\n--- Step 4: Intent Extraction ---")
    try:
        from app.nlp.intent import extract_intent
        transcript = "I'd like one paneer tikka and two chicken biryani please"
        intent = await extract_intent(transcript)
        print(f"  Transcript: '{transcript}'")
        print(f"  Intent type: {intent['intent_type']}")
        print(f"  Items: {json.dumps(intent['items'], indent=2)}")
        print(f"  Sentiment: {intent['sentiment']}")
        print(f"  Duration: {intent['duration_ms']:.0f}ms")
    except Exception as e:
        print(f"  ⚠ Skipped (Gemini API not available): {e}")

    # Step 5: Response Generation (requires Gemini API)
    print("\n--- Step 5: Response Generation ---")
    try:
        from app.nlp.response import generate_response
        order_json = {
            "items": [
                {"name": "Paneer Tikka", "quantity": 1},
                {"name": "Chicken Biryani", "quantity": 2},
            ],
            "intent_type": "order",
        }
        resp = await generate_response(order_json, upsell_suggestion="Cold Coffee")
        print(f"  Response: {resp['response_text']}")
        print(f"  Duration: {resp['duration_ms']:.0f}ms")
    except Exception as e:
        print(f"  ⚠ Skipped (Gemini API not available): {e}")

    # Step 6: TTS
    print("\n--- Step 6: Text-to-Speech ---")
    try:
        from app.voice.tts import synthesize_speech
        tts_result = await synthesize_speech(
            "Great choice! I have one paneer tikka and two chicken biryani. "
            "Would you like to add a cold coffee with that?"
        )
        print(f"  Audio size: {len(tts_result['audio_bytes'])} bytes")
        print(f"  Voice: {tts_result['voice']}")
        print(f"  Duration: {tts_result['duration_ms']:.0f}ms")
    except Exception as e:
        print(f"  ⚠ TTS failed: {e}")


async def demo_full_pipeline_simulation():
    """
    Simulate the full pipeline flow end-to-end.
    
    Since we can't pass real audio through the API in a script,
    we simulate the pipeline steps directly.
    """
    print("\n" + "=" * 60)
    print("  DEMO: Full Pipeline Simulation")
    print("=" * 60)

    customer_text = "Can I get one chicken biryani and a cold coffee please?"
    print(f"\n  Customer says: '{customer_text}'")

    # Simulate: customer text → intent → match → upsell → response → TTS
    total_ms = 0

    # Intent
    print("\n  [1/4] Extracting intent...")
    try:
        from app.nlp.intent import extract_intent
        intent = await extract_intent(customer_text)
        total_ms += intent["duration_ms"]
        print(f"        Intent: {intent['intent_type']} | Items: {len(intent['items'])}")
    except Exception as e:
        print(f"        ⚠ Using mock intent: {e}")
        intent = {
            "items": [
                {"name": "Chicken Biryani", "quantity": 1},
                {"name": "Cold Coffee", "quantity": 1},
            ],
            "intent_type": "order",
            "sentiment": "positive",
        }

    # Match
    print("  [2/4] Matching to menu...")
    from app.services.matching import match_items
    item_names = [i.get("name", "") for i in intent.get("items", [])]
    matched = match_items(item_names)
    matched_names = [m["matched_item"] for m in matched if m["matched_item"]]
    print(f"        Matched: {matched_names}")

    # Upsell
    print("  [3/4] Finding upsell...")
    from app.services.upsell_service import suggest_upsell
    upsell = suggest_upsell(matched_names)
    print(f"        Upsell: {upsell['suggestion']} ({upsell['reason']})")

    # Response + TTS
    print("  [4/4] Generating response & speech...")
    try:
        from app.nlp.response import generate_response
        from app.voice.tts import synthesize_speech

        resp = await generate_response(intent, upsell.get("suggestion"))
        total_ms += resp["duration_ms"]
        print(f"        Response: {resp['response_text']}")

        tts = await synthesize_speech(resp["response_text"])
        total_ms += tts["duration_ms"]
        print(f"        Audio: {len(tts['audio_bytes'])} bytes")
    except Exception as e:
        print(f"        ⚠ Skipped response/TTS: {e}")

    print(f"\n  Total processing time: {total_ms:.0f}ms")
    print("=" * 60)


async def main():
    """Run all demos."""
    print("\n🎯 AI Voice Copilot — Demo Script")
    print("=" * 60)

    await demo_individual_endpoints()
    await demo_full_pipeline_simulation()

    print("\n✅ Demo complete!")
    print("\nTo run the full API server:")
    print("  cd ai_service")
    print("  uvicorn app.main:app --reload")
    print("\nThen open: http://localhost:8000/docs")


if __name__ == "__main__":
    asyncio.run(main())
