import wave, io, json
import requests

buf = io.BytesIO()
with wave.open(buf, "wb") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(8000)
    wf.writeframes(b"\x00\x00" * 4000)
buf.seek(0)

r = requests.post("http://127.0.0.1:8010/api/audio/transcribe",
                  files={"file": ("test.wav", buf, "audio/wav")},
                  data={"duration": "0.5"}, timeout=10)
t = r.json()
print("transcribe:", t.get("session_id"), t.get("engine"), "text_len:", len(t.get("text", "")))

r2 = requests.post("http://127.0.0.1:8010/api/chat/messages",
                   json={"session_id": t["session_id"], "content": t["text"], "save_user": False},
                   timeout=15, stream=True)
body = r2.text
print("chat done:", '"type": "done"' in body)

msgs = requests.get(f"http://127.0.0.1:8010/api/sessions/{t['session_id']}/messages", timeout=10).json()
print("roles:", ",".join(m["role"] for m in msgs), "| user count:", sum(1 for m in msgs if m["role"] == "user"))
