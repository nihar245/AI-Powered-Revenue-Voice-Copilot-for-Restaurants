import httpx

text = (
    "Welcome to our restaurant! Your order of two Chicken Biryani, one Roti, "
    "and one Mango Lassi has been confirmed. The total comes to six hundred "
    "and twenty six rupees. Your food will be ready in approximately twenty "
    "minutes. Thank you for ordering with us!"
)

r = httpx.post("http://127.0.0.1:8000/voice/speak", json={"text": text}, timeout=60)
print(f"Status: {r.status_code}")
print(f"Audio size: {len(r.content)} bytes")
print(f"Content-Type: {r.headers.get('content-type')}")
print(f"X-Duration-Ms: {r.headers.get('x-duration-ms')}")

with open("test_long_audio.mp3", "wb") as f:
    f.write(r.content)
print("Saved to test_long_audio.mp3 - double-click to play!")
