from app.rag.prompt import SYSTEM_PROMPT    # بنجيب شخصية نور وقواعدها من ملف فريق الـ RAG
from app.rag.config import SYSTEM_DATE      # بنجيب "النهارده" بتاع داتا المشروع (19 سبتمبر 2026)

LIVE_PROMPT = SYSTEM_PROMPT + f"\n\nToday is {SYSTEM_DATE:%d %B %Y}."  # البرومبت نفسه + سطر في الآخر بالتاريخ