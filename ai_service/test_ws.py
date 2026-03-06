"""
Quick test of the WebSocket conversation endpoint.
Pipeline: Deepgram STT → Groq LLM → Deepgram TTS.
"""
import asyncio
import json
import time
import base64

import websockets

SERVER = "ws://localhost:8000/ws/conversation"


async def main():
    print("Connecting to", SERVER)
    async with websockets.connect(SERVER, open_timeout=30) as ws:
        # 1. Start session
        await ws.send(json.dumps({"type": "start"}))
        resp = json.loads(await ws.recv())
        print(f"[1] {resp['type']}: session_id={resp.get('session_id')}")
        assert resp["type"] == "session_started"

        # 2. Send text message — Turn 1
        t0 = time.perf_counter()
        await ws.send(json.dumps({"type": "text", "data": "I want one paneer tikka and two garlic naan"}))
        resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
        t1 = time.perf_counter()
        print(f"[2] Turn 1 ({(t1-t0)*1000:.0f}ms):")

        if resp["type"] == "response":
            print(f"    Agent: {resp.get('agent_text', '')[:120]}")
            audio_b64 = resp.get("audio_base64", "")
            if audio_b64:
                audio_bytes = base64.b64decode(audio_b64)
                print(f"    Audio: {len(audio_bytes)} bytes WAV")
            print(f"    Order: {resp.get('order')}")
        elif resp["type"] == "error":
            print(f"    ERROR: {resp.get('message')}")

        # 3. Turn 2 — follow-up order
        t0 = time.perf_counter()
        await ws.send(json.dumps({"type": "text", "data": "Also add one mango lassi please"}))
        resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
        t1 = time.perf_counter()
        print(f"[3] Turn 2 ({(t1-t0)*1000:.0f}ms):")

        if resp["type"] == "response":
            print(f"    Agent: {resp.get('agent_text', '')[:120]}")
            audio_b64 = resp.get("audio_base64", "")
            if audio_b64:
                audio_bytes = base64.b64decode(audio_b64)
                print(f"    Audio: {len(audio_bytes)} bytes WAV")
                with open("test_response.wav", "wb") as f:
                    f.write(audio_bytes)
                print("    Saved to test_response.wav")

        # 4. End session
        await ws.send(json.dumps({"type": "end"}))
        resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        print(f"[4] {resp['type']}")
        if resp["type"] == "session_ended":
            s = resp.get("summary", {})
            print(f"    Turns: {s.get('total_turns')}")
            print(f"    Order: {s.get('order')}")

    print("\n✅ WebSocket conversation test complete!")


if __name__ == "__main__":
    asyncio.run(main())
