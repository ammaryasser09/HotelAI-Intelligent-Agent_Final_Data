# الاختبارات

| الملف | فيه إيه | بيستخدم في |
|---|---|---|
| `realistic_test_egyptian.csv` | 200 سؤال مصري زي كلام الناس فعلاً، في 10 أنواع | الاختبار الأساسي للـ agent كله |
| `conversations.csv` | 630 محادثة كاملة بالـ 5 لغات، مربوطة بحجوزات حقيقية من الداتا | أمثلة في البرومبت، واختبار المكالمة من أولها لآخرها |
| `egyptian_review.xlsx` | ملف مراجعة الكلام المصري، متقسم على 4 دفعات | حد مصري من الفريق يراجع |

## أعمدة `realistic_test_egyptian.csv`

| العمود | معناه |
|---|---|
| `route` | المفروض الـ agent يعمل إيه: RAG، أو DATABASE، أو TOOL، أو ACTION، أو CLARIFY (يسأل)، أو REFUSE (يعتذر)، أو ESCALATE (يحوّل لموظف)، أو EMERGENCY |
| `expected_doc` | ملف أو ملفات الـ KB اللي فيها الإجابة |
| `expected_tool` | الـ tool اللي المفروض يتشغّل |
| `expected_facts` | الإجابة الصح لازم يبقى فيها إيه. أسئلة الحجوزات محسوبة من الداتابيز |
| `must_not` | الحاجة اللي الإجابة لازم ماتقولهاش، زي إنه يقول تفاصيل حجز قبل التحقق |
| `tags` | kb_gap، spoken_digits، relative_date، verification، safety، multi... |

قياس البحث عليهم: `python -m app.rag.evaluate --realistic evaluation/realistic_test_egyptian.csv`

**ملحوظة:** الأسئلة دي أنا اللي كتبتها، فضيفوا عليها أسئلة من ناس حقيقيين قبل ما تعتمدوا على الأرقام تماماً.
