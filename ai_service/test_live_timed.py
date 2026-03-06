"""
Timed multi-turn test: measures latency for each component.
"""
import asyncio
import time
from google import genai
from google.genai import types

API_KEY = "AIzaSyBSqvU6uDtHeFX5hKGUjHKcPOE69j1g-ms"
MODEL  = "gemini-2.5-flash-native-audio-latest"

client = genai.Client(api_key=API_KEY)


async def timed_turn(session, text: str, turn_num: int):
    t0 = time.perf_counter()
    await session.send_client_content(
        turns=types.Content(role="user", parts=[types.Part(text=text)]),
        turn_complete=True,
    )
    t_sent = time.perf_counter()

    chunks = 0
    total_bytes = 0
    t_first_chunk = None
    async for resp in session.receive():
        sc = resp.server_content
        if sc is None:
            continue
        if sc.model_turn:
            for p in sc.model_turn.parts:
                if p.inline_data and p.inline_data.data:
                    chunks += 1
                    total_bytes += len(p.inline_data.data)
                    if t_first_chunk is None:
                        t_first_chunk = time.perf_counter()
        if sc.turn_complete:
            break

    t_done = time.perf_counter()

    ttfb = (t_first_chunk - t_sent) if t_first_chunk else 0
    total = t_done - t0
    audio_sec = total_bytes / (24000 * 2)  # 24kHz 16-bit mono

    print(f"  Turn {turn_num}: '{text}'")
    print(f"    Time to first byte (TTFB): {ttfb*1000:.0f}ms")
    print(f"    Total response time:       {total*1000:.0f}ms")
    print(f"    Audio chunks: {chunks}, bytes: {total_bytes}, duration: {audio_sec:.1f}s")
    print()
    return {"turn": turn_num, "ttfb_ms": ttfb*1000, "total_ms": total*1000, "audio_sec": audio_sec}


async def main():
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(
            parts=[types.Part(text="You are a restaurant order assistant. Keep answers short (1-2 sentences).")],
        ),
    )

    t_connect_start = time.perf_counter()
    async with client.aio.live.connect(model=MODEL, config=config) as session:
        t_connect = time.perf_counter() - t_connect_start
        print(f"Session connect time: {t_connect*1000:.0f}ms\n")

        results = []
        results.append(await timed_turn(session, "Hi, I want two chicken biryani", 1))
        results.append(await timed_turn(session, "Add one cold coffee", 2))
        results.append(await timed_turn(session, "That's all, what's my total?", 3))

    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Session connect: {t_connect*1000:.0f}ms")
    for r in results:
        print(f"Turn {r['turn']}: TTFB={r['ttfb_ms']:.0f}ms, Total={r['total_ms']:.0f}ms, Audio={r['audio_sec']:.1f}s")
    avg_ttfb = sum(r['ttfb_ms'] for r in results) / len(results)
    avg_total = sum(r['total_ms'] for r in results) / len(results)
    print(f"Avg TTFB: {avg_ttfb:.0f}ms, Avg Total: {avg_total:.0f}ms")


if __name__ == "__main__":
    asyncio.run(main())
