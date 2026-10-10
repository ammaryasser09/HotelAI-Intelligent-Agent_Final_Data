#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rebuild the RAG files after editing the knowledge base or the FAQ:

    python scripts/build_rag.py

  knowledge_base/*.txt     -> rag/corpus.jsonl     one chunk per numbered section, prefixed with
                                                    "Nile Pearl Hotel / <DOC TITLE> / <section>"
  rag/hotel_faq_gold.csv   -> rag/faq_index.jsonl  the answered questions the retriever searches
                                                    (train split) and evaluates on (val / test)
Then run  python scripts/check_data.py
"""
import csv, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB = os.path.join(ROOT, 'knowledge_base')
CORPUS = os.path.join(ROOT, 'rag', 'corpus.jsonl')
GOLD = os.path.join(ROOT, 'rag', 'hotel_faq_gold.csv')
FAQ = os.path.join(ROOT, 'rag', 'faq_index.jsonl')
MIN_BODY = 120
SEC = re.compile(r'^\s*\d+\.\s+\S')

def sections(path):
    lines = open(path, encoding='utf-8').read().split('\n')
    title = lines[1].strip()
    body = [l.rstrip() for l in lines[2:] if l.strip() != title]
    out, name, buf = [], None, []
    for l in body:
        if SEC.match(l):
            if name or any(x.strip() for x in buf): out.append((name, buf))
            name, buf = l.strip(), []
        else:
            buf.append(l)
    out.append((name, buf))
    res = []
    for name, buf in out:
        text = '\n'.join(buf).strip()
        if name is None:
            first, _, rest = text.partition('\n')
            name, text = (first.strip(), rest.strip()) if len(first) < 40 and first.strip() else ('Overview', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        if text: res.append([name, text])
    return title, res

def corpus_chunks():
    chunks = []
    for fn in sorted(f for f in os.listdir(KB) if f.endswith('.txt')):
        title, secs = sections(os.path.join(KB, fn))
        merged = []
        for name, text in secs:
            if merged and (len(text) < MIN_BODY or len(merged[-1][1]) < MIN_BODY):
                merged[-1][0] += ' + ' + name
                merged[-1][1] += f'\n\n{name}\n\n{text}'
            else:
                merged.append([name, text])
        for i, (name, text) in enumerate(merged):
            full = f'Nile Pearl Hotel\n{title}\n{name}\n\n{text}'
            chunks.append({'chunk_id': f'{fn[:-4]}::{i:02d}', 'doc_id': fn, 'doc_title': title, 'section': name,
                           'language': 'English', 'text': full, 'char_len': len(full)})
    return chunks

def faq_rows():
    out = []
    for r in csv.DictReader(open(GOLD, encoding='utf-8')):
        ans = r['answer_egyptian'] if r['language'] == 'Arabic-Egyptian' and r['answer_egyptian'] else r['answer']
        out.append({'query_id': r['faq_id'], 'query': r['question'], 'language': r['language'], 'intent_id': r['intent_id'],
                    'gold_doc_id': r['source_doc'], 'gold_answer': ans, 'split': r['split']})
    return out

def dump(rows):
    return ''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in rows)

if __name__ == '__main__':
    c = corpus_chunks(); open(CORPUS, 'w', encoding='utf-8').write(dump(c))
    q = faq_rows(); open(FAQ, 'w', encoding='utf-8').write(dump(q))
    print(f'rag/corpus.jsonl: {len(c)} chunks from {len({x["doc_id"] for x in c})} documents')
    print(f'rag/faq_index.jsonl: {len(q)} questions ({sum(x["split"] == "train" for x in q)} train / '
          f'{sum(x["split"] == "val" for x in q)} val / {sum(x["split"] == "test" for x in q)} test)')
