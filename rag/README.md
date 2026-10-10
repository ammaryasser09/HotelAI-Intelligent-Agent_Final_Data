# ملفات الـ RAG

| الملف | فيه إيه |
|---|---|
| `corpus.jsonl` | الـ 44 ملف بتوع `knowledge_base/` متقطعين 146 chunk. دي اللي بتتعمل عليها embedding |
| `hotel_faq_gold.csv` | 3,965 سؤال وإجابة بالـ 5 لغات (منهم 385 مصري)، كل واحد معاه المستند اللي جاوب منه |
| `faq_index.jsonl` | نفس الأسئلة بالشكل اللي الـ retriever بيقراه. **متعدلهوش بإيدك**، بيتبني من `hotel_faq_gold.csv` |

## أعمدة `hotel_faq_gold.csv`

| العمود | معناه |
|---|---|
| `language` | English, Arabic, French, Russian, Arabic-Egyptian |
| `answer` | الإجابة. في الصفوف المصري دي الإجابة الفصحى المرجعية |
| `answer_egyptian` | الإجابة بالمصري (للصفوف المصري بس) |
| `source_doc` | ملف الـ KB اللي فيه الإجابة، أو `out_of_scope_policy` للأسئلة اللي بره شغل الفندق |
| `response_mode` | knowledge_answer، أو customer_service، أو safe_refusal_or_redirect (رفض مؤدب)، أو escalate_to_human (تحويل لموظف) |
| `requires_tool` | true لو الإجابة محتاجة داتا حية أو إجراء (حجز معين، متاح، إلغاء...) |
| `question_style` | templated للأسئلة المتولدة بقوالب، وnatural للباقي. ممكن تستبعد templated من التقييم |
| `split` | train بيدخل في الـ FAQ index، وval وtest للتقييم بس. نفس المعلومة عمرها ما تبقى في train وtest مع بعض |
| `fact_id` | نفس المعلومة بالـ 4 لغات بتاخد نفس الرقم، و`check_data.py` بيتأكد إن أرقامها متطابقة |

بعد أي تعديل: `python scripts/build_rag.py` وبعدين `python scripts/check_data.py`.
