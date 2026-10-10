# -*- coding: utf-8 -*-
"""
Retrieval evaluation per language on held-out questions.

    python3 -m app.rag.evaluate --mode bm25              # no downloads
    python3 -m app.rag.evaluate --mode hybrid            # BM25 + BGE-M3 (the target setup)
    python3 -m app.rag.evaluate --mode dense --no-faq    # KB-only dense baseline

The FAQ index is built from the train split only; queries come from the test split, so
no evaluated question is in the index. "unseen" repeats the metrics on test questions whose
answer (the fact) never appears in train in that language — the honest worst case.
A hit = the gold document (or 'out_of_scope_policy') ranked in the top k.
"""
import argparse, json, os, sys
from collections import Counter, defaultdict
from .config import FAQ, DENSE_MODEL
from .retriever import HybridRetriever

LANGS = ['English', 'French', 'Russian', 'Arabic', 'Arabic-Egyptian']

def run(mode, use_faq, embedder, split, realistic=None):
    r = HybridRetriever(mode=mode, embedder=embedder, use_faq=use_faq)
    rows = [json.loads(l) for l in open(FAQ, encoding='utf-8')]
    seen = {(q['language'], q['gold_answer']) for q in rows if q['split'] == 'train'}
    evalq = [q for q in rows if q['split'] == split]
    if realistic:
        import csv
        evalq = [{'query': x['question'], 'language': 'Arabic-Egyptian', 'gold_doc_id': x['expected_doc'], 'gold_answer': ''}
                 for x in csv.DictReader(open(realistic, encoding='utf-8'))
                 if ('RAG' in x['route'] or x['route'] == 'REFUSE') and x['expected_doc']]
    agg = defaultdict(Counter)
    for q in evalq:
        ranked = r.search(q['query'])['ranked_docs']
        gold = set(q['gold_doc_id'].split(';'))           # a hit on any expected document counts
        rank = min((ranked.index(g) + 1 for g in gold if g in ranked), default=None)
        keys = [q['language'], 'ALL'] + (['unseen:' + q['language'], 'unseen:ALL'] if (q['language'], q['gold_answer']) not in seen and not realistic else [])
        for k in keys:
            c = agg[k]; c['n'] += 1
            for kk in (1, 3, 5): c[f'r{kk}'] += bool(rank and rank <= kk)
            c['mrr'] += 1 / rank if rank and rank <= 10 else 0
    name = f'{mode}{"" if mode == "bm25" else " / " + (embedder if isinstance(embedder, str) else embedder.name)} | FAQ index: {"train" if use_faq else "off"}'
    print(f'\nRetriever: {name} | queries: {"realistic test set" if realistic else split} ({len(evalq)})')
    print(f'{"":22} {"n":>5} {"R@1":>6} {"R@3":>6} {"R@5":>6} {"MRR":>6}')
    for k in LANGS + ['ALL'] + [f'unseen:{l}' for l in LANGS] + ['unseen:ALL']:
        c = agg.get(k)
        if c: print(f'{k:22} {c["n"]:>5} {c["r1"]/c["n"]:6.3f} {c["r3"]/c["n"]:6.3f} {c["r5"]/c["n"]:6.3f} {c["mrr"]/c["n"]:6.3f}')
    return agg

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', default='hybrid', choices=['bm25', 'dense', 'hybrid'])
    ap.add_argument('--no-faq', action='store_true', help='KB index only (baseline)')
    ap.add_argument('--embedder', default=DENSE_MODEL, help="'BAAI/bge-m3' or 'hashing' (offline smoke test only)")
    ap.add_argument('--split', default='test', choices=['val', 'test'])
    ap.add_argument('--realistic', help='CSV of the realistic test set (evaluation/realistic_test_egyptian.csv)')
    a = ap.parse_args()
    run(a.mode, not a.no_faq, a.embedder, a.split, a.realistic)
