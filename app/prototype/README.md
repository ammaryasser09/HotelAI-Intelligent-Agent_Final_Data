# تجربة المشروع كله — Prototype

صوت ← Whisper ← RAG ← LLM (+ tools) ← رد بصوت مصري.

**أسهل طريقة:** افتح `HotelAI_Prototype.ipynb` على Google Colab، واختار T4 GPU، وارفع `HotelAI_Clean.zip`، وشغّل الخلايا بالترتيب. كله ببلاش ومن غير API key.

| الملف | فيه إيه |
|---|---|
| `agent.py` | الـ agent: بيدوّر، وبيشغّل الـ tools (من الـ router أو من الموديل)، وبيبعت للـ LLM. شغال مع Qwen على Colab أو مع أي API شبه OpenAI. `agent.login(account_id)` بيخليه ضيف عامل login و`agent.logout()` بيرجعه زائر، والـ tools دايماً بتاخد الحساب من الـ session مش من كلام الموديل |
| `speech.py` | Whisper بيعرف اللغة لوحده، وصوت الرد حسب اللغة، وحساب WER |
| `test_agent.py` | اختبار أوتوماتيك على الأسئلة الواقعية وعلى الـ 5 لغات |
| `HotelAI_Prototype.ipynb` | الـ notebook الجاهز |

**الشخصية:** اسمها "نور" (الاسم في `app/rag/config.py`). بتبدأ المكالمة بترحيب الفندق، وبتتكلم بالعامية مع المصري (حضرتك، يا فندم، تحت أمرك)، وبلغة العميل مع الباقيين. الشخصية والأمثلة في `app/rag/prompt.py`.

ده نموذج للتجربة، مش الشكل النهائي. في المشروع الحقيقي الـ tools هتبقى API في الـ Backend على الداتابيز.
