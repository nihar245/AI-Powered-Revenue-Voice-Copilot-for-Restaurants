"""Quick test for language detection + matching + conversation pipeline."""
import sys
import asyncio
import json
import time

# --- Test 1: Language Detection ---
print("=" * 60)
print("TEST 1: Language Detection")
print("=" * 60)

from app.voice.language import detect_language_from_text

tests = [
    ("two chicken biryani and one cold coffee", "en"),
    ("mujhe do biryani chahiye aur ek coffee", "hinglish"),
    ("bhai ek butter naan dedo", "hinglish"),
    ("mane be biryani aapjo", "gu"),
    ("kemcho mane ek rotli aapjo", "gu"),
    # Devanagari Hindi
    ("\u092e\u0941\u091d\u0947 \u090f\u0915 \u092c\u093f\u0930\u092f\u093e\u0928\u0940 \u0926\u0947\u0928\u093e", "hi"),
    # Gujarati script
    ("\u0aae\u0aa8\u0ac7 \u0aac\u0ac7 \u0aac\u0abf\u0ab0\u0aaf\u0abe\u0aa8\u0ac0 \u0a86\u0aaa\u0acb", "gu"),
]

all_pass = True
for text, expected in tests:
    result = detect_language_from_text(text)
    ok = "PASS" if result == expected else "FAIL"
    if result != expected:
        all_pass = False
    print(f"  [{ok}] '{text[:50]}' => {result} (expected {expected})")

print()

# --- Test 2: Alias-aware Matching ---
print("=" * 60)
print("TEST 2: Alias-aware Menu Matching")
print("=" * 60)

from app.services.matching import match_item

alias_tests = [
    ("biryani", "Chicken Biryani"),
    ("thandi coffee", "Cold Coffee"),
    ("makhan naan", "Butter Naan"),
    ("rotli", "Roti"),
    ("chapati", "Roti"),
    ("daal makhani", "Dal Makhani"),
    ("lassi", "Mango Lassi"),
    ("dosa", "Masala Dosa"),
]

for spoken, expected in alias_tests:
    result = match_item(spoken)
    matched = result["matched_item"] if result else None
    ok = "PASS" if matched == expected else "FAIL"
    if matched != expected:
        all_pass = False
    print(f"  [{ok}] '{spoken}' => {matched} (expected {expected})")

print()
print("=" * 60)
if all_pass:
    print("ALL DETECTION + MATCHING TESTS PASSED!")
else:
    print("SOME TESTS FAILED - check above")
print("=" * 60)
print()

# --- Test 3: Conversations (requires server running) ---
if "--conv" not in sys.argv:
    print("Skipping conversation tests. Run with --conv to include.")
    sys.exit(0)

import websockets

async def test_conv(text, label):
    start = time.perf_counter()
    async with websockets.connect(
        "ws://127.0.0.1:8000/ws/conversation",
        ping_interval=None, open_timeout=30,
    ) as ws:
        await ws.send(json.dumps({"type": "start"}))
        r = json.loads(await ws.recv())

        await ws.send(json.dumps({"type": "text", "data": text}))
        r = json.loads(await asyncio.wait_for(ws.recv(), timeout=180))
        elapsed = time.perf_counter() - start

        lang = r.get("language", "?")
        agent = r.get("agent_text", "")
        order = r.get("order", {})
        items = order.get("items", [])

        print(f"[{label}] {elapsed:.1f}s | lang={lang}")
        print(f"  Agent: {agent[:200]}")
        if items:
            for i in items:
                qty = i["quantity"]
                name = i["name"]
                print(f"    {qty}x {name}")
            print(f"    Total: Rs{order.get('total', 0)}")
        print()

        await ws.send(json.dumps({"type": "end"}))
        await asyncio.wait_for(ws.recv(), timeout=10)

print("TEST 3: English conversation")
asyncio.run(test_conv("two chicken biryani and one cold coffee", "ENGLISH"))

print("TEST 4: Hinglish conversation")
asyncio.run(test_conv("bhai mujhe do butter naan chahiye aur ek dal makhani", "HINGLISH"))

print("TEST 5: Gujarati conversation")
asyncio.run(test_conv("mane ek chicken biryani aapjo", "GUJARATI"))
