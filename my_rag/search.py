import json
import re
import numpy as np
from rank_bm25 import BM25Okapi
from my_rag.config import CHUNKS_FILE, VECTORS_FILE, BM25_K1, BM25_B, SEARCH_TOP_K, RETRIEVE_N, RRF_K, BM25_WEIGHT
from my_rag.chunking import load_model

DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u0640]")
LETTERS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه"})
WORD = re.compile(r"\w+")


def normalize(text):
    text = text.lower()
    text = DIACRITICS.sub("", text)
    return text.translate(LETTERS)


def tokenize(text):
    return WORD.findall(normalize(text))


def _load_chunks():
    chunks = []
    with open(CHUNKS_FILE, encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line))
    return chunks


_chunks = _load_chunks()
_vectors = np.load(VECTORS_FILE).astype(np.float32)
_corpus = []
for _c in _chunks:
    _corpus.append(tokenize(_c["text"]))
_bm25 = BM25Okapi(_corpus, k1=BM25_K1, b=BM25_B)
_model = load_model()
_model.encode(["warm up"], normalize_embeddings=True)


def _bm25_scores(question):
    return _bm25.get_scores(tokenize(question))


def _dense_scores(question):
    q = _model.encode([question], normalize_embeddings=True)[0].astype(np.float32)
    return _vectors @ q


def hybrid_rank(question, n=RETRIEVE_N):
    dense = _dense_scores(question)
    lists = [(1.0, dense)]
    if BM25_WEIGHT > 0:
        lists.append((BM25_WEIGHT, _bm25_scores(question)))
    fused = {}
    for weight, scores in lists:
        order = np.argsort(-scores)[:100]
        rank = 0
        for i in order:
            if scores[i] <= 0:
                continue
            rank += 1
            fused[i] = fused.get(i, 0) + weight / (RRF_K + rank)
    best = sorted(fused, key=fused.get, reverse=True)[:n]
    return best, dense


def _answer_keys(chunk):
    keys = []
    if chunk["fact_id"]:
        keys.append(chunk["fact_id"])
    text = chunk["text"]
    if "\nA: " in text:
        text = text.split("\nA: ", 1)[1]
    keys.append(normalize(text))
    return keys


def search(question: str, top_k: int = SEARCH_TOP_K) -> list[dict]:
    try:
        if not question or not question.strip():
            return []
        best, dense = hybrid_rank(question)
        results = []
        seen = set()
        for i in best:
            keys = _answer_keys(_chunks[i])
            if any(k in seen for k in keys):
                continue
            seen.update(keys)
            results.append({
                "text": _chunks[i]["text"],
                "source": _chunks[i]["source"],
                "score": round(float(dense[i]), 4),
            })
            if len(results) == top_k:
                break
        return results
    except Exception:
        return []


if __name__ == "__main__":
    while True:
        q = input("Question (Enter to stop): ").strip()
        if not q:
            break
        for r in search(q):
            print("   ", r["score"], r["source"], "|", r["text"][:70].replace("\n", " "))
        print()