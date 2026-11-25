import asyncio
import inspect
import json
import logging
import os

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from app.api.security import read_access_token

router = APIRouter(tags=["Nour voice agent"])
logger = logging.getLogger("hotel_api")
NOUR = {}


def load_nour():
    if not NOUR:
        from google import genai
        from google.genai import types
        from app.llm import config, prompts, tools
        from app.rag.tools import _account
        NOUR.update(client=genai.Client(api_key=config.GEMINI_API_KEY), types=types, config=config,
                    prompt=prompts.LIVE_PROMPT, tools=tools, account=_account)
    return NOUR


def dev_mode():
    return os.getenv("NOUR_DEV") == "1"


if dev_mode() or os.getenv("NOUR_PRELOAD") == "1":
    load_nour()


def session_note(nour, account_id):
    if not account_id:
        return "SESSION: the caller is a visitor, not logged in."
    found = nour["account"](account_id)
    return f"SESSION: the caller is logged in as {found['full_name'] if found else 'unknown'}."


def make_config(nour, account_id):
    types = nour["types"]
    return {
        "response_modalities": ["AUDIO"],
        "output_audio_transcription": {},
        "input_audio_transcription": {},
        "speech_config": {"voice_config": {"prebuilt_voice_config": {"voice_name": nour["config"].VOICE}}},
        "realtime_input_config": {
            "automatic_activity_detection": {"start_of_speech_sensitivity": types.StartSensitivity.START_SENSITIVITY_LOW}
        },
        "system_instruction": nour["prompt"] + "\n\n" + session_note(nour, account_id),
        "tools": [{"function_declarations": nour["tools"].DECLARATIONS}],
    }


def log_turn(nour, line, guest, agent):
    nour["tools"].log_message(line, "guest", guest)
    nour["tools"].log_message(line, "agent", agent)


def background(fn, *args):
    asyncio.get_running_loop().run_in_executor(None, fn, *args)


async def run_tool(nour, session, websocket, call, account_id, line):
    fn = nour["tools"].FUNCTIONS[call.name]
    args = dict(call.args)
    if "account_id" in inspect.signature(fn).parameters:
        args["account_id"] = account_id
    if "call" in inspect.signature(fn).parameters:
        args["call"] = line
    try:
        result = await asyncio.to_thread(fn, **args)
    except Exception as e:
        result = {"ok": False, "reason": str(e)}
    await session.send_tool_response(function_responses=[
        nour["types"].FunctionResponse(id=call.id, name=call.name, response={"result": result})
    ])
    background(nour["tools"].log_action, line, call.name, dict(call.args), result)
    await websocket.send_json({"type": "tool", "name": call.name})
    if not isinstance(result, dict):
        return
    api_url = nour["tools"].API_URL
    if result.get("payment_url"):
        await websocket.send_json({"type": "payment", "url": result["payment_url"], "amount": result.get("pay_now"),
                                   "before": result.get("pay_before"), "booking": result.get("booking_id")})
    if result.get("photos"):
        await websocket.send_json({"type": "photos", "photos": [api_url + p["image"] for p in result["photos"]]})
    if result.get("images"):
        await websocket.send_json({"type": "photos", "photos": [api_url + p for p in result["images"].values()]})
    if result.get("handoff"):
        await websocket.send_json({"type": "handoff", "mode": result["handoff"], "staff": result.get("staff_name"),
                                   "call_id": line["id"], "chat_token": line.get("chat_token")})


async def from_browser(nour, websocket, session, turn):
    while True:
        message = await websocket.receive()
        if message["type"] == "websocket.disconnect":
            return
        if message.get("bytes"):
            await session.send_realtime_input(audio=nour["types"].Blob(data=message["bytes"], mime_type="audio/pcm;rate=16000"))
        elif message.get("text"):
            try:
                data = json.loads(message["text"])
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict) or data.get("type") != "text":
                continue
            text = str(data.get("text", "")).strip()[:2000]
            if text:
                turn["guest"].append(text)
                await session.send_realtime_input(text=text)


async def to_browser(nour, websocket, session, turn, account_id, line):
    while True:
        async for response in session.receive():
            content = response.server_content
            if content and content.interrupted:
                await websocket.send_json({"type": "interrupted"})
            elif response.data:
                await websocket.send_bytes(response.data)
            if content and content.input_transcription and content.input_transcription.text:
                turn["guest"].append(content.input_transcription.text)
                await websocket.send_json({"type": "guest", "text": content.input_transcription.text})
            if content and content.output_transcription and content.output_transcription.text:
                turn["agent"].append(content.output_transcription.text)
                await websocket.send_json({"type": "agent", "text": content.output_transcription.text})
            if content and content.turn_complete:
                guest, agent = "".join(turn["guest"]), "".join(turn["agent"])
                turn["guest"].clear()
                turn["agent"].clear()
                background(log_turn, nour, line, guest, agent)
                await websocket.send_json({"type": "turn"})
            if response.tool_call:
                for call in response.tool_call.function_calls:
                    await run_tool(nour, session, websocket, call, account_id, line)


@router.websocket("/ws/nour")
async def nour_socket(websocket: WebSocket, token: str = "", account: str = ""):
    """A voice or text call with Nour. The browser sends 16 kHz PCM audio (binary) or {"type": "text"};
    it receives 24 kHz PCM audio (binary) and JSON events. No token: the caller is a visitor."""
    account_id = None
    if token:
        try:
            account_id = str(read_access_token(token).account_id)
        except HTTPException:
            await websocket.close(code=4401)
            return
    elif account and dev_mode():
        account_id = str(account)
    await websocket.accept()
    try:
        await call_nour(websocket, account_id)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception("Nour call failed")
        try:
            await websocket.send_json({"type": "closed", "reason": f"{type(e).__name__}: {e}"})
            await websocket.close(code=1011)
        except Exception:
            pass


async def call_nour(websocket, account_id):
    try:
        nour = await asyncio.to_thread(load_nour)
    except Exception as e:
        logger.exception("Nour could not be loaded")
        await websocket.send_json({"type": "closed", "reason": f"NOUR_NOT_AVAILABLE: {type(e).__name__}: {e}"})
        await websocket.close(code=1011)
        return
    line = await asyncio.to_thread(nour["tools"].start_call, account_id, "voice")
    await websocket.send_json({"type": "ready", "call_id": line["id"], "logged_in": bool(account_id)})
    turn = {"guest": [], "agent": []}
    try:
        async with nour["client"].aio.live.connect(model=nour["config"].MODEL, config=make_config(nour, account_id)) as session:
            tasks = [asyncio.create_task(from_browser(nour, websocket, session, turn)),
                     asyncio.create_task(to_browser(nour, websocket, session, turn, account_id, line))]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            for task in done:
                if task.exception() and not isinstance(task.exception(), WebSocketDisconnect):
                    logger.error("Nour call stopped: %r", task.exception())
                    try:
                        await websocket.send_json({"type": "closed", "reason": f"{type(task.exception()).__name__}: {task.exception()}"})
                    except Exception:
                        pass
    finally:
        guest, agent = "".join(turn["guest"]), "".join(turn["agent"])
        await asyncio.to_thread(log_turn, nour, line, guest, agent)
        await asyncio.to_thread(nour["tools"].end_call, line)


PAGE = """<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nour call test</title>
<style>
body { font-family: system-ui, sans-serif; max-width: 720px; margin: 24px auto; padding: 0 16px; background: #f7f5f0; color: #222; }
h1 { font-size: 22px; }
.row { display: flex; gap: 8px; align-items: center; margin: 8px 0; flex-wrap: wrap; }
button { padding: 8px 16px; font-size: 15px; border-radius: 8px; border: 1px solid #888; background: #fff; cursor: pointer; }
button.go { background: #1f6f5c; color: #fff; border-color: #1f6f5c; }
input { padding: 8px; font-size: 15px; border-radius: 8px; border: 1px solid #aaa; }
#log { background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 12px; min-height: 240px; white-space: pre-wrap; line-height: 1.7; }
.guest { color: #1d4ed8; } .agent { color: #111; } .sys { color: #888; font-size: 13px; }
#extras img { width: 160px; border-radius: 8px; margin: 4px; }
#extras a { display: inline-block; margin: 8px 0; padding: 8px 12px; background: #fff4d6; border-radius: 8px; }
</style>
</head>
<body>
<h1>مكالمة مع نور (صفحة تجربة)</h1>
<div class="row">
  <label>Token <input id="token" placeholder="من /auth/login" size="14"></label>
  <label>أو Account <input id="account" value="997" size="5"></label>
  <button class="go" id="start">ابدأ المكالمة</button>
  <button id="stop" disabled>اقفل</button>
  <span id="state" class="sys">مقفولة</span>
</div>
<div class="row">
  <input id="text" placeholder="أو اكتب هنا..." size="40" disabled>
  <button id="send" disabled>ابعت</button>
</div>
<div id="log"></div>
<div id="extras"></div>
<script>
let ws = null, ctxIn = null, ctxOut = null, stream = null, node = null, playTime = 0, sources = [], line = null, who = null;
const $ = id => document.getElementById(id);

function say(kind, text) {
  if (who !== kind) {
    line = document.createElement("div");
    line.className = kind;
    line.textContent = kind === "guest" ? "أنت: " : kind === "agent" ? "نور: " : "";
    $("log").appendChild(line);
    who = kind;
  }
  line.textContent += text;
  $("log").scrollTop = $("log").scrollHeight;
}

function note(text) { who = null; say("sys", text); who = null; }

function play(buffer) {
  const pcm = new Int16Array(buffer);
  const samples = new Float32Array(pcm.length);
  for (let k = 0; k < pcm.length; k++) samples[k] = pcm[k] / 32768;
  const audio = ctxOut.createBuffer(1, samples.length, 24000);
  audio.copyToChannel(samples, 0);
  const source = ctxOut.createBufferSource();
  source.buffer = audio;
  source.connect(ctxOut.destination);
  const at = playTime < ctxOut.currentTime ? ctxOut.currentTime + 0.25 : playTime;
  source.start(at);
  playTime = at + audio.duration;
  sources.push(source);
  source.onended = () => { sources = sources.filter(s => s !== source); };
}

function silence() {
  sources.forEach(s => { try { s.stop(); } catch (e) {} });
  sources = [];
  playTime = 0;
}

function onMessage(event) {
  if (typeof event.data !== "string") { play(event.data); return; }
  const m = JSON.parse(event.data);
  if (m.type === "ready") note((m.logged_in ? "مسجّل دخول. " : "زائر. ") + (m.call_id ? "Call log: " + m.call_id : "Call log: off"));
  else if (m.type === "guest" || m.type === "agent") say(m.type, m.text);
  else if (m.type === "interrupted") { silence(); note("[interrupted]"); }
  else if (m.type === "turn") who = null;
  else if (m.type === "tool") note("[tool] " + m.name);
  else if (m.type === "payment") {
    const a = document.createElement("a");
    a.href = m.url; a.target = "_blank";
    a.textContent = "ادفع " + (m.amount ?? "") + " جنيه للحجز " + (m.booking ?? "") + (m.before ? " قبل " + m.before : "");
    $("extras").appendChild(a);
  }
  else if (m.type === "photos") m.photos.forEach(src => { const img = document.createElement("img"); img.src = src; $("extras").appendChild(img); });
  else if (m.type === "handoff") note("[handoff] " + m.mode + (m.staff ? " - " + m.staff : ""));
  else if (m.type === "closed") note("[call closed] " + m.reason);
}

async function start() {
  $("start").disabled = true;
  note("بيتصل...");
  ctxOut = new AudioContext({ sampleRate: 24000 });
  const token = $("token").value.trim();
  const query = token ? "token=" + encodeURIComponent(token) : "account=" + encodeURIComponent($("account").value);
  ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/nour?${query}`);
  ws.binaryType = "arraybuffer";
  ws.onmessage = onMessage;
  ws.onerror = () => note("WebSocket error");
  ws.onclose = e => { note("المكالمة اتقفلت (" + e.code + ")"); stop(); };
  ws.onopen = () => {
    $("state").textContent = "متصلة";
    $("stop").disabled = false; $("text").disabled = false; $("send").disabled = false;
    startMic();
  };
}

async function startMic() {
  try {
    note("بيطلب المايك...");
    stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 } });
    ctxIn = new AudioContext();
    const mic = ctxIn.createMediaStreamSource(stream);
    node = ctxIn.createScriptProcessor(4096, 1, 1);
    const ratio = ctxIn.sampleRate / 16000;
    node.onaudioprocess = e => {
      if (!ws || ws.readyState !== 1) return;
      const input = e.inputBuffer.getChannelData(0);
      const pcm = new Int16Array(Math.floor(input.length / ratio));
      for (let k = 0; k < pcm.length; k++) pcm[k] = Math.max(-1, Math.min(1, input[Math.floor(k * ratio)])) * 0x7fff;
      ws.send(pcm.buffer);
    };
    mic.connect(node);
    node.connect(ctxIn.destination);
    $("state").textContent = "شغالة، اتكلم";
    note("المايك شغال");
  } catch (e) {
    note("المايك مش شغال: " + e.message + " (تقدر تكتب)");
  }
}

function stop() {
  const open = ws;
  ws = null;
  if (open && open.readyState === 1) open.close();
  silence();
  if (node) node.disconnect();
  if (stream) stream.getTracks().forEach(t => t.stop());
  if (ctxIn) ctxIn.close();
  if (ctxOut) ctxOut.close();
  node = stream = ctxIn = ctxOut = null;
  $("state").textContent = "مقفولة";
  $("start").disabled = false; $("stop").disabled = true; $("text").disabled = true; $("send").disabled = true;
}

function sendText() {
  const text = $("text").value.trim();
  if (!text || !ws || ws.readyState !== 1) return;
  ws.send(JSON.stringify({ type: "text", text }));
  who = null; say("guest", text); who = null;
  $("text").value = "";
}

$("start").onclick = () => start().catch(e => note("Error: " + e.message));
$("stop").onclick = stop;
$("send").onclick = sendText;
$("text").onkeydown = e => { if (e.key === "Enter") sendText(); };
</script>
</body>
</html>"""


@router.get("/nour/test", response_class=HTMLResponse, include_in_schema=False)
async def nour_test_page():
    if not dev_mode():
        raise HTTPException(status_code=404, detail={"reason": "NOT_FOUND"})
    return PAGE
