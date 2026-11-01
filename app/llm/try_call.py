import asyncio
import time
from google import genai
from google.genai import types
from app.llm.config import GEMINI_API_KEY, MODEL, THINKING_LEVEL
from app.llm.prompts import LIVE_PROMPT
from app.llm.tools import DECLARATIONS, FUNCTIONS

client = genai.Client(api_key=GEMINI_API_KEY)

CONFIG = {
    "response_modalities": ["AUDIO"],
    "output_audio_transcription": {},
    "system_instruction": LIVE_PROMPT,
    "tools": [{"function_declarations": DECLARATIONS}],
}
if "extended-thinking" in MODEL:
    CONFIG["thinking_config"] = {"thinking_level": THINKING_LEVEL}

STATE = {"sent": time.time(), "speaking": False}


def since():
    return f"{time.time() - STATE['sent']:.1f}s"


def describe(msg):
    d = msg.model_dump(exclude_none=True)
    sc = d.get("server_content", {})
    extra = [k for k in d if k != "server_content"]
    extra += [k for k in sc if k not in ("model_turn", "output_transcription")]
    return f"{extra} status={sc.get('interaction_status')}" if extra else None


async def run_tool(session, call):
    print(f"\n[tool {since()}] {call.name} {call.args}")
    try:
        result = await asyncio.to_thread(FUNCTIONS[call.name], **call.args)
    except Exception as e:
        result = {"ok": False, "reason": str(e)}
    await session.send_tool_response(function_responses=[
        types.FunctionResponse(id=call.id, name=call.name, response={"result": result})
    ])


async def listen(session):
    while True:
        async for response in session.receive():
            info = describe(response)
            if info:
                print(f"\n[debug {since()}] {info}")
            content = response.server_content
            if content and content.output_transcription and content.output_transcription.text:
                if not STATE["speaking"]:
                    print("\nNour: ", end="")
                    STATE["speaking"] = True
                print(content.output_transcription.text, end="", flush=True)
            if content and content.turn_complete:
                STATE["speaking"] = False
                print("\nYou: ", end="", flush=True)
            if response.tool_call:
                for call in response.tool_call.function_calls:
                    await run_tool(session, call)


async def talk(session):
    while True:
        text = await asyncio.to_thread(input)
        if text.strip().lower() == "exit":
            return
        STATE["sent"] = time.time()
        await session.send_realtime_input(text=text)


async def main():
    print(f"Model: {MODEL}")
    async with client.aio.live.connect(model=MODEL, config=CONFIG) as session:
        print("Nour is on the line (type exit to hang up)\nYou: ", end="", flush=True)
        listener = asyncio.create_task(listen(session))
        await talk(session)
        listener.cancel()


if __name__ == "__main__":
    asyncio.run(main())