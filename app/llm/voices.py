import asyncio
import os
import sys
import wave
from google import genai
from app.llm.config import GEMINI_API_KEY, MODEL

VOICES = sys.argv[1:] or ["Kore", "Aoede", "Leda", "Zephyr", "Puck", "Charon", "Fenrir", "Orus"]
TEXTS = {
    "ar": "\u0623\u0647\u0644\u0627\u064b \u0628\u062d\u0636\u0631\u062a\u0643 \u0641\u064a \u0641\u0646\u062f\u0642 \u0646\u0627\u064a\u0644 \u0628\u064a\u0631\u0644\u060c \u0645\u0639\u0627\u0643 \u0646\u0648\u0631. \u0627\u0644\u0641\u0637\u0627\u0631 \u0628\u0648\u0641\u064a\u0647 \u0628\u0623\u0644\u0641 \u0648\u0645\u062a\u064a\u0646 \u062c\u0646\u064a\u0647 \u0644\u0644\u0641\u0631\u062f\u060c \u0645\u0646 \u0633\u0628\u0639\u0629 \u0644\u062d\u062f \u0639\u0634\u0631\u0629 \u0648\u0646\u0635 \u0627\u0644\u0635\u0628\u062d. \u0623\u064a \u062e\u062f\u0645\u0629 \u062a\u0627\u0646\u064a\u0629 \u0623\u0642\u062f\u0631 \u0623\u0633\u0627\u0639\u062f \u062d\u0636\u0631\u062a\u0643 \u0641\u064a\u0647\u0627\u061f",
    "en": "Welcome to Nile Pearl Hotel, this is Nour. Breakfast is a buffet for 1,200 pounds per person, from 7 to 10:30 in the morning. Is there anything else I can help you with?",
}
INSTRUCTION = "Read the user's text aloud exactly as written, as a warm and polite female hotel receptionist. Do not add, answer or change anything."
FOLDER = "voices"

client = genai.Client(api_key=GEMINI_API_KEY)


async def speak(voice, lang, text):
    config = {
        "response_modalities": ["AUDIO"],
        "system_instruction": INSTRUCTION,
        "speech_config": {"voice_config": {"prebuilt_voice_config": {"voice_name": voice}}},
    }
    audio = b""
    async with client.aio.live.connect(model=MODEL, config=config) as session:
        await session.send_realtime_input(text=text)
        async for response in session.receive():
            if response.data:
                audio += response.data
            if response.server_content and response.server_content.turn_complete:
                break
    path = os.path.join(FOLDER, f"{voice}_{lang}.wav")
    with wave.open(path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(24000)
        f.writeframes(audio)
    return path, len(audio) / 48000


async def main():
    os.makedirs(FOLDER, exist_ok=True)
    print(f"Model: {MODEL}  voices: {', '.join(VOICES)}")
    for voice in VOICES:
        for lang, text in TEXTS.items():
            try:
                path, seconds = await speak(voice, lang, text)
                print(f"  {path}  {seconds:.1f}s" + ("  (empty)" if seconds == 0 else ""))
            except Exception as e:
                print(f"  {voice} {lang}: ERROR {e}")
            await asyncio.sleep(1)
    print(f"Done. Open the folder: {os.path.abspath(FOLDER)}")


if __name__ == "__main__":
    asyncio.run(main())
