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

## How it works

```
question → BGE-M3 vector → outside the hotel? → yes: []
                                              → no: top 20 closest chunks → remove duplicates → top 5
```

1. **Index** (`chunking.py`): 44 knowledge-base files split by numbered sections (230 chunks) + 2,618 training FAQ answers = **2,848 chunks**, each turned into a 1024-number vector by BGE-M3 and saved in `index/`.
2. **Out-of-scope check** (`search.py`): the question is compared with example off-topic questions (anchors). If it is closer to them than to any hotel chunk by more than `OOS_MARGIN`, we return `[]`.
3. **Retrieval** (`search.py`): cosine similarity between the question vector and all chunk vectors.
4. **Dedup**: chunks with the same `fact_id` or the same answer text are kept once.

## Files

| file | role |
|---|---|
| `config.py` | all settings (paths, model, weights, margins) |
| `bm25_search.py` | keyword search (BM25), first experiment |
| `dense_search.py` | meaning search (BGE-M3), first experiment |
| `chunking.py` | builds the index (`index/chunks.jsonl`, `index/vectors.npy`) |
| `search.py` | the `search()` function used by the LLM team |
| `evaluate.py` | measures accuracy and speed |
| `notebooks/` | every experiment with its results |

## Rebuild after changing the data

If any file in `knowledge_base/` or `rag/hotel_faq_gold.csv` changes:

```bash
python -m my_rag.chunking
python -m my_rag.evaluate
```

## Results

Measured on `evaluation/realistic_test_egyptian.csv` (105 real questions with a known answer file):

| metric | value |
|---|---|
| correct file in top 5 (Recall@5) | **88%** |
| correct file in top 20 (Recall@20) | **97%** |
| average time per question (RTX 3060) | **~0.02s** |
| slowest question | 0.055s |
| off-topic questions blocked | **27 / 27** |

## Decisions (all measured)

| tried | result | decision |
|---|---|---|
| Hybrid BM25 + BGE-M3 (7 weight settings) | every BM25 weight lowered accuracy (weight 1.0 → 79%) | `BM25_WEIGHT = 0.0` |
| Cosine threshold for off-topic | could not separate in-scope and off-topic questions | replaced with anchors |
| Reranker `bge-reranker-v2-m3` | 88% → 92% (+4), 5x slower, weak on Egyptian Arabic | not used (rule: +5 and < 0.5s) |

## Known data gaps

- Egyptian questions about loyalty tiers have no answer yet.
- Shisha / hookah is not covered in the smoking policy.
- Some old answers still ask for booking reference + last name, which conflicts with the login design.

## Team

RAG team: Ammar & Sondos.