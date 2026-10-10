# -*- coding: utf-8 -*-
"""
Show what the agent would receive for a question.

    python3 -m app.rag.demo "الفطار بكام؟"
    python3 -m app.rag.demo --mode hybrid "Can I cancel for free?"
"""
import argparse, json
from .retriever import HybridRetriever
from .prompt import build_messages, detect_language

ap = argparse.ArgumentParser()
ap.add_argument('question'); ap.add_argument('--mode', default='bm25', choices=['bm25', 'dense', 'hybrid'])
ap.add_argument('--show-prompt', action='store_true')
a = ap.parse_args()
res = HybridRetriever(mode=a.mode).search(a.question)
print('language :', detect_language(a.question))
print('documents:', res['docs'], '| out of scope' if res['out_of_scope'] else '')
for c in res['chunks']: print(f'  chunk  {c["chunk_id"]:32} {c["section"]}')
for e in res['faq_examples']: print(f'  faq    [{e["language"]}] {e["query"]}  ->  {e["gold_answer"][:90]}')
if a.show_prompt:
    for m in build_messages(a.question, res): print(f'\n--- {m["role"]} ---\n{m["content"]}')
