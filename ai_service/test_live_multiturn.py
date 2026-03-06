"""
Minimal test: multi-turn text conversation via Gemini Live API.
Tests whether the model responds to a second message after the first turn_complete.
"""
import asyncio
from google import genai
from google.genai import types

API_KEY = "AIzaSyBSqvU6uDtHeFX5hKGUjHKcPOE69j1g-ms"
MODEL  = "gemini-2.5-flash-native-audio-latest"

client = genai.Client(api_key=API_KEY)


async def main():
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(
            parts=[types.Part(text="You are a restaurant order assistant. Keep answers very short.")],
        ),
    )

    async with client.aio.live.connect(model=MODEL, config=config) as session:
        print("Session opened.")

        # ── Turn 1 ──
        print("\n--- TURN 1: sending text ---")
        await session.send_client_content(
            turns=types.Content(role="user", parts=[types.Part(text="Hi, I want a chicken biryani")]),
            turn_complete=True,
        )

        chunks_t1 = 0
        async for resp in session.receive():
            sc = resp.server_content
            if sc is None:
                print(f"  [non-content msg: {resp}]")
                continue
            if sc.model_turn:
                for p in sc.model_turn.parts:
                    if p.inline_data and p.inline_data.data:
                        chunks_t1 += 1
            if sc.turn_complete:
                print(f"  Turn 1 complete: {chunks_t1} audio chunks")
                break

        # ── Turn 2 ──
        print("\n--- TURN 2: sending text ---")
        await session.send_client_content(
            turns=types.Content(role="user", parts=[types.Part(text="Add one cold coffee")]),
            turn_complete=True,
        )

        chunks_t2 = 0
        print("  Waiting for response...")
        async for resp in session.receive():
            sc = resp.server_content
            if sc is None:
                print(f"  [non-content msg: {resp}]")
                continue
            if sc.model_turn:
                for p in sc.model_turn.parts:
                    if p.inline_data and p.inline_data.data:
                        chunks_t2 += 1
                        if chunks_t2 == 1:
                            print(f"  First chunk received!")
            if sc.turn_complete:
                print(f"  Turn 2 complete: {chunks_t2} audio chunks")
                break

        # ── Turn 3 ──
        print("\n--- TURN 3: sending text ---")
        await session.send_client_content(
            turns=types.Content(role="user", parts=[types.Part(text="That's all, what's my total?")]),
            turn_complete=True,
        )

        chunks_t3 = 0
        async for resp in session.receive():
            sc = resp.server_content
            if sc is None:
                print(f"  [non-content msg: {resp}]")
                continue
            if sc.model_turn:
                for p in sc.model_turn.parts:
                    if p.inline_data and p.inline_data.data:
                        chunks_t3 += 1
            if sc.turn_complete:
                print(f"  Turn 3 complete: {chunks_t3} audio chunks")
                break

    print("\n✅ Multi-turn test passed!")


if __name__ == "__main__":
    asyncio.run(main())
