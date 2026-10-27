import csv
import json
import re
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from my_rag.config import (
    KB_DIR, FAQ_FILE, INDEX_DIR, CHUNKS_FILE, VECTORS_FILE,
    MODELS_DIR, DENSE_MODEL, DENSE_BATCH_SIZE, DENSE_MAX_LENGTH,
)

SECTION = re.compile(r"^\d+\.\s+\S")


def split_file(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    doc_title = lines[1].strip()
    parts = []
    title = "Overview"
    body = []
    for line in lines[2:]:
        if line.strip() == doc_title:
            continue
        if SECTION.match(line):
            parts.append((title, "\n".join(body).strip()))
            title = line.strip()
            body = []
        else:
            body.append(line)
    parts.append((title, "\n".join(body).strip()))

    chunks = []
    for title, text in parts:
        if not text:
            continue
        chunks.append({
            "chunk_id": f"{path.stem}::{len(chunks):02d}",
            "kind": "kb",
            "source": path.name,
            "section": title,
            "language": "English",
            "fact_id": "",
            "text": doc_title + " - " + title + "\n" + text,
        })
    return chunks


def kb_chunks():
    chunks = []
    for path in sorted(KB_DIR.glob("*.txt")):
        chunks.extend(split_file(path))
    return chunks


def faq_chunks():
    chunks = []
    with open(FAQ_FILE, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["split"] != "train":
                continue
            if row["requires_tool"] == "true":
                continue
            if row["source_doc"] == "out_of_scope_policy":
                continue
            answer = row["answer"]
            if row["language"] == "Arabic-Egyptian" and row["answer_egyptian"]:
                answer = row["answer_egyptian"]
            chunks.append({
                "chunk_id": row["faq_id"],
                "kind": "faq",
                "source": row["source_doc"],
                "section": row["intent_name"],
                "language": row["language"],
                "fact_id": row["fact_id"],
                "text": "Q: " + row["question"] + "\nA: " + answer,
            })
    return chunks


def load_model():
    if torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"
    model = SentenceTransformer(DENSE_MODEL, cache_folder=str(MODELS_DIR), device=device)
    if device != "cpu":
        model.half()
    model.max_seq_length = DENSE_MAX_LENGTH
    return model


if __name__ == "__main__":
    chunks = kb_chunks() + faq_chunks()
    print(len(chunks), "chunks")

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print("saved", CHUNKS_FILE)

    texts = []
    for c in chunks:
        texts.append(c["text"])
    model = load_model()
    vectors = model.encode(texts, normalize_embeddings=True, batch_size=DENSE_BATCH_SIZE, show_progress_bar=True)
    np.save(VECTORS_FILE, vectors.astype(np.float16))
    print("saved", VECTORS_FILE, vectors.shape)

