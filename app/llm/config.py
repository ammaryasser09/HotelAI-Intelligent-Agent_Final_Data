import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODELS = [m.strip() for m in os.getenv("NOUR_MODELS", "gemini-3.8-live,gemini-3.1-flash-live-preview").split(",") if m.strip()]
MODEL = MODELS[0]
THINKING_LEVEL = "low"
ACCOUNT_ID = 997
VOICE = "Aoede"


@asynccontextmanager
async def connect(client, make_config):
    failed = []
    for model in MODELS:
        opening = client.aio.live.connect(model=model, config=make_config(model))
        try:
            session = await opening.__aenter__()
        except Exception as e:
            failed.append(f"{model}: {type(e).__name__}: {e}")
            print(f"[model {model} did not answer, trying the next one] {e}")
            continue
        try:
            yield session, model
        except BaseException as e:
            if not await opening.__aexit__(type(e), e, e.__traceback__):
                raise
        else:
            await opening.__aexit__(None, None, None)
        return
    raise ConnectionError("no live model answered: " + " | ".join(failed))
