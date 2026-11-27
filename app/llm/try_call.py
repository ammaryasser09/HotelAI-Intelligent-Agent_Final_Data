import asyncio
import inspect
import sys
import threading
import time
from google import genai
from google.genai import types
from app.llm.config import GEMINI_API_KEY, MODELS, THINKING_LEVEL, ACCOUNT_ID, VOICE, connect
from app.llm.prompts import LIVE_PROMPT
from app.llm.tools import FUNCTIONS, declarations, start_call, log_message, log_action, end_call
from app.rag.tools import _account

VOICE_MODE = len(sys.argv) > 1 and sys.argv[1] == "voice"
MUTE_WHILE_SPEAKING = "speaker" in sys.argv[2:]
MIC_RATE = 16000
SPEAKER_RATE = 24000
CHUNK = 1600
PREBUFFER = SPEAKER_RATE * 2 // 4
OUT_BLOCK = 2400

client = genai.Client(api_key=GEMINI_API_KEY)


def session_note():
    if ACCOUNT_ID is None:
        return "SESSION: the caller is a visitor, not logged in."
    account = _account(ACCOUNT_ID)
    name = account["full_name"] if account else "unknown"
    return f"SESSION: the caller is logged in as {name}."


def make_config(model):
    config = {
        "response_modalities": ["AUDIO"],
        "output_audio_transcription": {},
        "speech_config": {"voice_config": {"prebuilt_voice_config": {"voice_name": VOICE}}},
        "system_instruction": LIVE_PROMPT + "\n\n" + session_note(),
        "tools": [{"function_declarations": declarations(model)}],
    }
    if VOICE_MODE:
        config["input_audio_transcription"] = {}
        config["realtime_input_config"] = {
            "automatic_activity_detection": {"start_of_speech_sensitivity": types.StartSensitivity.START_SENSITIVITY_LOW}
        }
    if "extended-thinking" in model:
        config["thinking_config"] = {"thinking_level": THINKING_LEVEL}
    return config


STATE = {"call": None, "sent": time.time(), "speaking": False, "hearing": False, "played": 0.0, "arrived": 0.0, "primed": False,
         "guest": [], "agent": []}
PLAYBACK = bytearray()
LOCK = threading.Lock()


def since():
    return f"{time.time() - STATE['sent']:.1f}s"


def play(outdata, frames, time_info, status):
    need = frames * 2
    with LOCK:
        ready = len(PLAYBACK) >= PREBUFFER or (PLAYBACK and time.time() - STATE["arrived"] > 0.3)
        if not STATE["primed"] and ready:
            STATE["primed"] = True
        chunk = b""
        if STATE["primed"]:
            chunk = bytes(PLAYBACK[:need])
            del PLAYBACK[:need]
            if len(chunk) < need:
                STATE["primed"] = False
    if chunk:
        STATE["played"] = time.time()
    outdata[:] = chunk + b"\x00" * (need - len(chunk))


def background(fn, *args):
    asyncio.get_running_loop().run_in_executor(None, fn, *args)


def log_turn(guest, agent):
    log_message(STATE["call"], "guest", guest)
    log_message(STATE["call"], "agent", agent)


def save_turn(wait=False):
    guest, agent = "".join(STATE["guest"]), "".join(STATE["agent"])
    STATE["guest"].clear()
    STATE["agent"].clear()
    if wait:
        log_turn(guest, agent)
    else:
        background(log_turn, guest, agent)


async def run_tool(session, call):
    print(f"\n[tool {since()}] {call.name} {call.args}")
    fn = FUNCTIONS[call.name]
    args = dict(call.args)
    if "account_id" in inspect.signature(fn).parameters:
        args["account_id"] = None if ACCOUNT_ID is None else str(ACCOUNT_ID)
    if "call" in inspect.signature(fn).parameters:
        args["call"] = STATE["call"]
    try:
        result = await asyncio.to_thread(fn, **args)
    except Exception as e:
        result = {"ok": False, "reason": str(e)}
    if call.name != "search_hotel_info":
        print(f"[result] {result}")
    background(log_action, STATE["call"], call.name, dict(call.args), result)
    await session.send_tool_response(function_responses=[
        types.FunctionResponse(id=call.id, name=call.name, response={"result": result})
    ])


async def listen(session):
    try:
        await hear(session)
    except Exception as e:
        print(f"\n[call closed] {e}")


async def hear(session):
    while True:
        async for response in session.receive():
            content = response.server_content
            if content and content.interrupted:
                with LOCK:
                    PLAYBACK.clear()
                    STATE["primed"] = False
                print("\n[interrupted]", flush=True)
                STATE["speaking"] = False
            elif VOICE_MODE and response.data:
                with LOCK:
                    PLAYBACK.extend(response.data)
                    STATE["arrived"] = time.time()
            if content and content.input_transcription and content.input_transcription.text:
                if not STATE["hearing"]:
                    STATE["sent"] = time.time()
                    print("\nYou: ", end="")
                    STATE["hearing"] = True
                print(content.input_transcription.text, end="", flush=True)
                STATE["guest"].append(content.input_transcription.text)
            if content and content.output_transcription and content.output_transcription.text:
                if not STATE["speaking"]:
                    print("\nNour: ", end="")
                    STATE["speaking"] = True
                    STATE["hearing"] = False
                print(content.output_transcription.text, end="", flush=True)
                STATE["agent"].append(content.output_transcription.text)
            if content and content.turn_complete:
                save_turn()
                STATE["speaking"] = False
                STATE["hearing"] = False
                print("\n" if VOICE_MODE else "\nYou: ", end="", flush=True)
            if response.tool_call:
                for call in response.tool_call.function_calls:
                    await run_tool(session, call)


async def talk(session):
    while True:
        text = await asyncio.to_thread(input)
        if text.strip().lower() == "exit":
            return
        STATE["sent"] = time.time()
        STATE["guest"].append(text)
        try:
            await session.send_realtime_input(text=text)
        except Exception:
            print("[call closed] run the command again for a new call")
            return


async def speak(session):
    import sounddevice as sd
    loop = asyncio.get_running_loop()
    mic = asyncio.Queue()

    def record(indata, frames, time_info, status):
        loop.call_soon_threadsafe(mic.put_nowait, bytes(indata))

    with sd.RawInputStream(samplerate=MIC_RATE, channels=1, dtype="int16", blocksize=CHUNK, callback=record), \
            sd.RawOutputStream(samplerate=SPEAKER_RATE, channels=1, dtype="int16", blocksize=OUT_BLOCK, latency="high", callback=play):
        print("Speak now (Ctrl+C to hang up)" + ("  mic is muted while Nour speaks" if MUTE_WHILE_SPEAKING else ""))
        while True:
            data = await mic.get()
            if MUTE_WHILE_SPEAKING and time.time() - STATE["played"] < 0.5:
                data = b"\x00" * len(data)
            await session.send_realtime_input(audio=types.Blob(data=data, mime_type=f"audio/pcm;rate={MIC_RATE}"))


async def main():
    print(f"Models: {' -> '.join(MODELS)}  voice: {VOICE}  mode: {'voice' if VOICE_MODE else 'text'}")
    STATE["call"] = await asyncio.to_thread(start_call, None if ACCOUNT_ID is None else str(ACCOUNT_ID),
                                            "voice" if VOICE_MODE else "text")
    print(f"Call log: {STATE['call']['id'] or 'off (hotel server not running)'}")
    try:
        async with connect(client, make_config) as (session, model):
            print(f"Connected to {model}")
            listener = asyncio.create_task(listen(session))
            if VOICE_MODE:
                await speak(session)
            else:
                print("Nour is on the line (type exit to hang up)\nYou: ", end="", flush=True)
                await talk(session)
            listener.cancel()
    finally:
        save_turn(wait=True)
        end_call(STATE["call"])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCall ended")
