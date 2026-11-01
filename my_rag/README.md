# my_rag — Hotel Knowledge Search (RAG)

Search engine for the Nile Pearl Hotel voice agent.
Given a guest question in any supported language, it returns the most relevant hotel information for the LLM to answer from.

## Quick start

```bash
git switch rag
pip install sentence-transformers rank_bm25
```

```python
from my_rag.search import search

results = search("الأوضة الديلوكس بتاخد كام فرد؟", top_k=5)
```

The first import downloads BGE-M3 (~2GB, once) into `models/` and loads it.
Import once at server start, not inside every request.

## Contract

```python
def search(question: str, top_k: int = 5) -> list[dict]
```

| key | meaning |
|---|---|
| `text` | the hotel information to give the LLM |
| `source` | file it came from (e.g. `room_types.txt`) |
| `score` | cosine similarity with the question (higher = closer) |

- Returns `[]` when the question is outside the hotel (outside restaurants, football, politics...).
- Never raises an error. Worst case it returns `[]`.
- Languages: Egyptian, Gulf, Modern Standard Arabic, English, French, Russian.

## Tip for the LLM team: write a clear query

Do not pass the guest's words as they are. Write the query yourself, with the topic in it:

| guest said | send to `search()` |
|---|---|
| أوصل للجولد إزاي؟ | إزاي أوصل لمستوى Gold في برنامج الولاء؟ |
| عايز دبل من 5 لـ 8، وفي جراج؟ والفطار بكام؟ | 3 calls: double room capacity / parking / breakfast price |
| بكام السويت تلات ليالي؟ | suite price per night |

Measured: `أوصل للجولد إزاي؟` returns `[]`, while `إزاي أوصل لمستوى Gold في برنامج الولاء؟` returns `loyalty_programs.txt` in all top 3.
English queries score highest because the knowledge base is written in English.

**Off-topic questions:** the LLM prompt must refuse off-topic questions itself, even when `search()` returns results (about 1 in 3 new off-topic questions passes the RAG check).
If `search()` returns `[]` for a question that sounds like a hotel question (e.g. the hotel restaurant), do not say "I can't help". Say you will check, or hand off to staff.

## How it works

```
question → BGE-M3 vector → outside the hotel? → yes: []
                                              → no: top 20 closest chunks → remove duplicates → top 5
```

1. **Index** (`chunking.py`): 44 knowledge-base files split by numbered sections (230 chunks) + 2,625 training FAQ answers = **2,855 chunks**, each turned into a 1024-number vector by BGE-M3 and saved in `index/`.
2. **Out-of-scope check** (`search.py`): the question is compared with example off-topic questions (anchors). If it is closer to them than to any hotel chunk by more than `OOS_MARGIN` (0.07), we return `[]`.
3. **Retrieval** (`search.py`): cosine similarity between the question vector and all chunk vectors.
4. **Dedup**: chunks with the same `fact_id` or the same answer text are kept once.
5. **Warm-up**: at load, the model encodes sentences of 1 to 64 words, so the first guest question is not slow.

## Files

| file | role |
|---|---|
| `config.py` | all settings (paths, model, weights, margins) |
| `bm25_search.py` | keyword search (BM25), first experiment |
| `dense_search.py` | meaning search (BGE-M3), first experiment |
| `chunking.py` | builds the index (`index/chunks.jsonl`, `index/vectors.npy`) |
| `search.py` | the `search()` function used by the LLM team |
| `evaluate.py` | measures accuracy and speed |
| `test_search.py` | contract tests + 10 test questions in 6 languages |
| `notebooks/` | every experiment with its results |

## Run the tests

```bash
pip install pytest
python -m pytest my_rag/test_search.py -v
```

Expected: `14 passed`.

## Rebuild after changing the data

If any file in `knowledge_base/` or `rag/hotel_faq_gold.csv` changes:

```bash
python -m my_rag.chunking
python -m my_rag.evaluate
python -m pytest my_rag/test_search.py -v
```

Close running notebooks first: a notebook kernel keeps models in GPU memory and slows everything down.

## Results

Measured on `evaluation/realistic_test_egyptian.csv` (105 real questions with a known answer file):

| metric | value |
|---|---|
| correct file in top 5 (Recall@5) | **90%** |
| correct file in top 20 (Recall@20) | **98%** |
| average time per question (RTX 3060 laptop) | **0.02s** |
| slowest question (RTX 3060 laptop) | 0.031s |
| average / slowest time (MacBook Air, 8GB) | 0.032s / 0.114s |
| off-topic questions blocked | **27 / 27** |

## Results by language

Measured on FAQ questions the index never saw (`val` + `test` splits, 1,221 questions):

| language | Recall@5 | correct questions wrongly blocked |
|---|---|---|
| English | 100% | 0 / 302 |
| Arabic (MSA) | 98% | 0 / 239 |
| French | 96% | 1 / 312 |
| Russian | 95% | 2 / 265 |
| Arabic-Egyptian | 79% (~88% counting answers found in another file) | 4 / 103 |

- Optimistic: train questions with the same answers are in the index.
- Egyptian is the weakest because the knowledge base is in English and Egyptian uses slang.
- Gulf Arabic is not in the FAQ; it is covered only in `test_search.py`.

## Off-topic check on new questions

15 new off-topic questions (Egyptian, Gulf, English, French, Russian), different from the anchors:

| `OOS_MARGIN` | correct blocked by mistake (of 1,326) | new off-topic caught (of 15) |
|---|---|---|
| **0.07** | **8 (0.6%)** | **10** |
| 0.10 | 3 | 8 |
| 0.15 | 0 | 4 |

Kept 0.07. The anchors catch about 2/3 of new off-topic questions, so `[]` is a helper, not the only guard.

## Decisions (all measured)

| tried | result | decision |
|---|---|---|
| Hybrid BM25 + BGE-M3 (7 weight settings) | every BM25 weight lowered accuracy (weight 1.0 → 79%) | `BM25_WEIGHT = 0.0` |
| Cosine threshold for off-topic | could not separate in-scope and off-topic questions | replaced with anchors |
| Reranker `bge-reranker-v2-m3` | 88% → 92% (+4), 5x slower, weak on Egyptian Arabic | not used (rule: +5 and < 0.5s) |
| `OOS_MARGIN` 0.05 / 0.06 / 0.07 / 0.08 | in-scope questions blocked up to 0.057, off-topic starts at 0.083 | `0.07` (middle of the gap) |
| 7 Egyptian FAQ rewordings (جولد، بوينتس، شيشة) with the same existing answers | 89% → 90%, Recall@20 97% → 98%, still 27/27 blocked | kept |
| Warm-up with 1 short sentence vs sentences of 1–64 words | Mac slowest question 0.804s → 0.114s | warm-up 1–64 words |

## Known limits

- Very short slang questions with no topic (e.g. `أوصل للجولد إزاي؟`) are not understood. The LLM should write a clear query (see the tip above).
- One sentence with several questions returns results for only part of it. The LLM should split it.
- About 1 in 3 new off-topic questions is not blocked; the LLM prompt must refuse them too.
- Some old answers still ask for booking reference + last name to change a booking, which conflicts with the login design (waiting for team decision). Linking a booking made outside (phone, agency, Booking.com) still uses reference + last name.

## Team

RAG team: Ammar & Sondos.