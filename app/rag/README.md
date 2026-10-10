# كود الـ RAG — `app/rag/`

```
الصوت (Whisper) ← نص ← retriever.search() ← prompt.build_messages() ← LLM (+ tools) ← نص ← الصوت
```

| الملف | بيعمل إيه |
|---|---|
| `retriever.py` | بيدوّر في الـ KB **وفي** أسئلة الـ FAQ (الـ train بس، بالـ 5 لغات)، ويرجّع أحسن المستندات، وأحسن الـ chunks، وأسئلة شبه السؤال. ولو السؤال بره شغل الفندق بيرفع علامة `out_of_scope` |
| `text.py`، `bm25.py` | بحث بالكلمات مع توحيد كتابة العربي (أ/إ/آ ← ا، ى ← ي، ة ← ه) |
| `embedder.py` | BGE-M3 للبحث بالمعنى |
| `prompt.py` | شخصية نور والبرومبت، وبناء الرسالة للـ LLM، والترحيب والختام الثابتين |
| `router.py` | بيطلّع من كلام العميل رقم الحجز، والاسم، وكود الخصم، ونوع الأوضة، والتواريخ، ويشغّل الـ tools بنفسه. ده عشان الموديلات الصغيرة بتنسى تستخدم الـ tools |
| `tools.py` | 9 tools بتقرا من `database/seed/`، والـ API لازم يعمل نفس السلوك بالظبط (نفس المنطق بالـ SQL في `database/queries.sql`) |
| `evaluate.py` | قياس البحث لكل لغة |
| `demo.py` | بيوريك الموديل هيستلم إيه لسؤال واحد |
| `config.py` | المسارات، واسم الموديل، وعدد النتايج، واسم نور |

```bash
python -m app.rag.evaluate --mode bm25          # من غير إنترنت
python -m app.rag.evaluate --mode hybrid        # BM25 + BGE-M3 (pip install sentence-transformers)
python -m app.rag.evaluate --realistic evaluation/realistic_test_egyptian.csv
python -m app.rag.demo "لو لغيت الحجز هيتخصم مني كام؟" --show-prompt
```

## قواعد الـ tools
- "النهارده" = `app_settings.system_date` (19 سبتمبر 2026).
- الحجز مايتقالش غير لما الرقم يطابق الاسم (عربي أو إنجليزي) أو آخر 4 أرقام في التليفون.
- الأوضة مشغولة لو عليها حجز مؤكد أو خلص بس، والأطفال بيتحسبوا في السعة.
- الـ tools مش بتكتب في الداتا. الحجز والإلغاء بيعملهم الـ Backend بعد ما نور تقول التكلفة والعميل يوافق.
