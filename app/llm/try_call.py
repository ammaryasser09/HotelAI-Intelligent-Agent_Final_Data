import asyncio                                                      # مكتبة الـ async
import time                                                         # ← جديد: عشان نقيس الوقت
from google import genai                                            # مكتبة Gemini
from google.genai import types                                      # أنواع جاهزة زي FunctionResponse
from app.llm.config import GEMINI_API_KEY, MODEL, THINKING_LEVEL    # إعداداتنا
from app.llm.prompts import LIVE_PROMPT                             # شخصية نور
from app.llm.tools import DECLARATIONS, FUNCTIONS                   # كروت الـ tools والدوال بتاعتها

client = genai.Client(api_key=GEMINI_API_KEY)                       # الوسيط اللي بيكلّم جوجل

CONFIG = {                                                          # إعدادات المكالمة
    "response_modalities": ["AUDIO"],                               # نور بترد بصوت
    "output_audio_transcription": {},                               # ونسخة مكتوبة من كلامها
    "system_instruction": LIVE_PROMPT,                              # وصف وظيفة نور
    "tools": [{"function_declarations": DECLARATIONS}],             # الـ tools المتاحة لنور
}
if "extended-thinking" in MODEL:                                    # لو الموديل بتاع التفكير بس
    CONFIG["thinking_config"] = {"thinking_level": THINKING_LEVEL}  # نضيف مستوى التفكير

STATE = {"sent": time.time(), "speaking": False}                    # ← جديد: إمتى بعتنا آخر رسالة، وهل نور بتتكلم دلوقتي

def since():                                                        # ← جديد: عدد الثواني من آخر رسالة بعتناها
    return f"{time.time() - STATE['sent']:.1f}s"                    # مثلاً "2.3s"

def describe(msg):                                                  # بيوصف الرسالة اللي جاية من جوجل
    d = msg.model_dump(exclude_none=True)                           # نحوّل الرسالة لـ dict ونشيل الفاضي
    sc = d.get("server_content", {})                                # جزء الكلام لو موجود
    extra = [k for k in d if k != "server_content"]                 # أي حاجة غير الكلام (tool_call مثلاً)
    extra += [k for k in sc if k not in ("model_turn", "output_transcription")]  # وأي حاجة جوه الكلام غير الصوت والنص
    return f"{extra} status={sc.get('interaction_status')}" if extra else None   # سطر مختصر، أو None لو صوت ونص بس

async def run_tool(session, call):                                  # بننفذ الـ tool اللي نور طلبتها
    print(f"\n[tool {since()}] {call.name} {call.args}")            # نطبع اسمها والبيانات ووقتها
    try:                                                            # نجرّب نشغّلها
        result = FUNCTIONS[call.name](**call.args)                  # نشغّل الدالة الحقيقية
    except Exception as e:                                          # لو حصل أي خطأ
        result = {"ok": False, "reason": str(e)}                    # نقول لنور إن فيه مشكلة
    await session.send_tool_response(function_responses=[          # نبعت النتيجة لنور
        types.FunctionResponse(id=call.id, name=call.name, response={"result": result})  # الـ id بيربط الرد بالطلب
    ])

async def listen(session):                                          # ← جديد: مهمة السماع، شغالة طول المكالمة
    while True:                                                     # للأبد، لحد ما نوقفها
        async for response in session.receive():                    # نستلم كل اللي جاي من نور
            info = describe(response)                               # نوصف الرسالة
            if info:                                                # لو فيها حاجة غير الصوت والنص
                print(f"\n[debug {since()}] {info}")                # نطبع الوصف ومعاه الوقت
            content = response.server_content                       # جزء الكلام
            if content and content.output_transcription:            # لو فيه نص من كلام نور
                if not STATE["speaking"]:                           # لو دي أول كلمة في الدور
                    print("\nNour: ", end="")                       # نكتب اسمها الأول
                    STATE["speaking"] = True                        # ونسجّل إنها بدأت تتكلم
                print(content.output_transcription.text, end="", flush=True)  # نطبع الكلام أول بأول
            if content and content.turn_complete:                   # لو نور خلّصت دورها
                STATE["speaking"] = False                           # الدور الجاي هيبدأ باسمها من جديد
                print("\nYou: ", end="", flush=True)                # نقولك إنك تقدر تكتب
            if response.tool_call:                                  # لو نور طلبت tool
                for call in response.tool_call.function_calls:      # ممكن أكتر من واحدة
                    await run_tool(session, call)                   # ننفذها ونرجّع النتيجة

async def talk(session):                                            # ← جديد: مهمة الكلام، بتاخد كلامك وتبعته
    while True:                                                     # نفضل نتكلم
        text = await asyncio.to_thread(input)                       # نستنى تكتب (من غير ما نوقف السماع)
        if text.strip().lower() == "exit":                          # لو كتبت exit
            return                                                  # نخرج من المهمة دي
        STATE["sent"] = time.time()                                 # نسجّل وقت الإرسال عشان نقيس
        await session.send_realtime_input(text=text)                # نبعت كلامك لنور

async def main():                                                   # الدالة الأساسية
    print(f"Model: {MODEL}")                                        # نطبع الموديل
    async with client.aio.live.connect(model=MODEL, config=CONFIG) as session:  # نفتح المكالمة
        print("Nour is on the line (type exit to hang up)\nYou: ", end="", flush=True)  # المكالمة بدأت
        listener = asyncio.create_task(listen(session))             # ← جديد: نشغّل السماع في الخلفية
        await talk(session)                                         # ← جديد: نتكلم لحد ما تكتب exit
        listener.cancel()                                           # ← جديد: نوقف السماع ونقفل

if __name__ == "__main__":                                          # لو شغلنا الملف ده مباشرة
    asyncio.run(main())                                             # نشغّل main