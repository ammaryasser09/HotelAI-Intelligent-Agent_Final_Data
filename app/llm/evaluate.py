import asyncio
import csv
import inspect
import re
import sys
import time
from google import genai
from google.genai import types
from app.llm.config import GEMINI_API_KEY, MODEL, THINKING_LEVEL
from app.llm.prompts import LIVE_PROMPT
from app.llm.tools import DECLARATIONS, FUNCTIONS
from app.rag.tools import _account

QUESTIONS = "evaluation/realistic_test_egyptian.csv"
WAIT_AFTER_TURN = 8
MAX_SECONDS = 45

client = genai.Client(api_key=GEMINI_API_KEY)


def session_note(account_id):
    if not account_id:
        return "SESSION: the caller is a visitor, not logged in."
    account = _account(account_id)
    name = account["full_name"] if account else "unknown"
    return f"SESSION: the caller is logged in as {name}."


def make_config(account_id):
    config = {
        "response_modalities": ["AUDIO"],
        "output_audio_transcription": {},
        "system_instruction": LIVE_PROMPT + "\n\n" + session_note(account_id),
        "tools": [{"function_declarations": DECLARATIONS}],
    }
    if "extended-thinking" in MODEL:
        config["thinking_config"] = {"thinking_level": THINKING_LEVEL}
    return config


def numbers(text):
    text = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    text = re.sub(r"(?<=\d)[,٬](?=\d{3})", "", text)
    return set(re.findall(r"\d+(?:\.\d+)?", text))


def facts_score(expected, answer):
    wanted = numbers(expected)
    if not wanted:
        return "-"
    found = wanted & numbers(answer)
    return f"{len(found)}/{len(wanted)}"


def tool_check(expected, called, route):
    if not expected or route.startswith("CLARIFY"):
        return "-"
    if expected not in FUNCTIONS:
        return "tool not built"
    return "yes" if expected in called else "no"


async def run_tool(session, call, account_id, state):
    fn = FUNCTIONS[call.name]
    args = dict(call.args)
    if "account_id" in inspect.signature(fn).parameters:
        args["account_id"] = account_id or None
    try:
        result = await asyncio.to_thread(fn, **args)
    except Exception as e:
        result = {"ok": False, "reason": str(e)}
    state["tools"].append(f"{call.name} {dict(call.args)}")
    state["names"].append(call.name)
    state["last"] = time.time()
    await session.send_tool_response(function_responses=[
        types.FunctionResponse(id=call.id, name=call.name, response={"result": result})
    ])


async def listen(session, account_id, state):
    while True:
        async for response in session.receive():
            state["last"] = time.time()
            content = response.server_content
            if content and content.output_transcription and content.output_transcription.text:
                if state["first"] is None:
                    state["first"] = time.time() - state["sent"]
                state["text"].append(content.output_transcription.text)
            if content and content.turn_complete:
                state["turns"] += 1
            if response.tool_call:
                for call in response.tool_call.function_calls:
                    await run_tool(session, call, account_id, state)


async def ask(row):
    account_id = row["account_id"].strip()
    state = {"text": [], "tools": [], "names": [], "turns": 0,
             "first": None, "sent": time.time(), "last": time.time()}
    async with client.aio.live.connect(model=MODEL, config=make_config(account_id)) as session:
        listener = asyncio.create_task(listen(session, account_id, state))
        state["sent"] = time.time()
        await session.send_realtime_input(text=row["question"])
        while True:
            await asyncio.sleep(0.5)
            now = time.time()
            if state["turns"] and state["text"] and now - state["last"] > WAIT_AFTER_TURN:
                break
            if now - state["sent"] > MAX_SECONDS:
                break
        listener.cancel()
    answer = "".join(state["text"]).strip()
    return {
        "test_id": row["test_id"],
        "category": row["category"],
        "route": row["route"],
        "question": row["question"],
        "answer": answer,
        "tools_called": " | ".join(state["tools"]),
        "expected_tool": row["expected_tool"],
        "tool_ok": tool_check(row["expected_tool"], state["names"], row["route"]),
        "expected_facts": row["expected_facts"],
        "facts_numbers": facts_score(row["expected_facts"], answer),
        "first_words_s": "" if state["first"] is None else f"{state['first']:.1f}",
        "correct": "",
        "invented": "",
        "notes": "",
    }


async def main():
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    with open(QUESTIONS, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))[start:start + count]
    out = f"evaluation/results_{MODEL}_{start + 1}-{start + len(rows)}.csv"
    print(f"Model: {MODEL}  questions {start + 1} to {start + len(rows)}  ->  {out}")
    results = []
    for i, row in enumerate(rows, 1):
        print(f"\n[{i}/{len(rows)}] {row['test_id']} {row['question']}")
        try:
            r = await ask(row)
        except Exception as e:
            r = {"test_id": row["test_id"], "category": row["category"],
                 "question": row["question"], "answer": f"ERROR {e}"}
        print(f"  Nour: {r.get('answer')}")
        print(f"  tools: {r.get('tools_called') or '-'}   tool_ok: {r.get('tool_ok', '-')}"
              f"   facts: {r.get('facts_numbers', '-')}   first words: {r.get('first_words_s', '-')}s")
        results.append(r)
        await asyncio.sleep(2)
    fields = ["test_id", "category", "route", "question", "answer", "tools_called", "expected_tool",
              "tool_ok", "expected_facts", "facts_numbers", "first_words_s",
              "correct", "invented", "notes"]
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)
    tools = [r for r in results if r.get("tool_ok") in ("yes", "no")]
    ok = sum(r["tool_ok"] == "yes" for r in tools)
    times = [float(r["first_words_s"]) for r in results if r.get("first_words_s")]
    print(f"\nSaved {out}")
    print(f"Right tool: {ok}/{len(tools)}")
    if times:
        print(f"Average time to first words: {sum(times) / len(times):.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
