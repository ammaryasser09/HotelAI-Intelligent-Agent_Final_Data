# -*- coding: utf-8 -*-
"""
Small automatic test of the whole agent on the realistic Egyptian questions.

    results, summary = run(agent, n=40)      # stratified sample: every category is represented

Scores (automatic, rough — read the answers yourself too; the CSV has everything):
  retrieval  the expected KB document is among the documents given to the LLM (RAG rows)
  route      the expected tool was called / a question was asked / the reception was named ...
  facts      share of the expected numbers (prices, times, counts) that appear in the answer
"""
import csv, os, re
from collections import defaultdict
from importlib import import_module
ROOT = import_module('app.rag.config').ROOT
TEST = os.path.join(ROOT, 'evaluation', 'realistic_test_egyptian.csv')
AR_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')

def numbers(s):
    s = s.translate(AR_DIGITS)
    return [float(x.replace(',', '')) for x in re.findall(r'\d[\d,]*(?:\.\d+)?', s) if x.replace(',', '')]

def facts_score(expected, answer):
    exp = [n for n in numbers(expected) if n >= 2 and n not in (2026, 2027)]
    if not exp: return None
    got = numbers(answer)
    hit = sum(any(abs(g - e) <= max(1, e * 0.01) for g in got) for e in exp)
    return round(hit / len(exp), 2)

def route_ok(row, r):
    tools = [t['tool'] for t in r['tools']]; a = r['answer']; route = row['route']
    if row['expected_tool'] and any(x in route for x in ('TOOL', 'DATABASE')):
        return row['expected_tool'] in tools
    if route.startswith('CLARIFY'):
        leaked = any(t['tool'] == 'find_booking' and t['result'].get('ok') for t in r['tools'])
        return ('؟' in a or '?' in a) and not leaked
    if route == 'EMERGENCY': return bool(re.search(r'2794\s?5500|استقبال|ريسبشن|الطوارئ|الإسعاف', a))
    if route == 'ESCALATE': return 'escalate_to_human' in tools or bool(re.search(r'موظف|مدير|حد من|أحولك|هحولك|تحويل', a))
    if route == 'REFUSE': return not tools
    return None

def sample(rows, n):
    by = defaultdict(list)
    for r in rows: by[r['category']].append(r)
    out, i = [], 0
    while len(out) < min(n, len(rows)):
        for cat in by:
            if i < len(by[cat]) and len(out) < n: out.append(by[cat][i])
        i += 1
    return out

def run(agent, n=40, out='prototype_results.csv', show=True):
    rows = sample(list(csv.DictReader(open(TEST, encoding='utf-8'))), n)
    res = []
    for k, row in enumerate(rows, 1):
        agent.reset(); r = agent.ask(row['question'])
        exp_docs = [d for d in row['expected_doc'].split(';') if d]
        res.append({**row, 'answer': r['answer'], 'tools_called': ' '.join(t['tool'] for t in r['tools']),
                    'docs_given': ' '.join(r['docs']), 'seconds': r['seconds'],
                    'retrieval_ok': (any(d in r['docs'] for d in exp_docs) if exp_docs and 'RAG' in row['route'] else ''),
                    'route_ok': route_ok(row, r), 'facts': facts_score(row['expected_facts'], r['answer'])})
        if show: print(f"[{k}/{len(rows)}] {row['question']}\n   → {r['answer'][:160]}  ({r['seconds']}s)")
    with open(out, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(res[0].keys())); w.writeheader(); w.writerows(res)
    summary = defaultdict(lambda: defaultdict(list))
    for x in res:
        for key in ('retrieval_ok', 'route_ok', 'facts'):
            if x[key] not in ('', None): summary[x['category']][key].append(float(x[key]))
        summary[x['category']]['seconds'].append(x['seconds'])
    table = [{'category': c, 'n': len(v['seconds']),
              **{k: (round(sum(v[k]) / len(v[k]), 2) if v[k] else '-') for k in ('retrieval_ok', 'route_ok', 'facts')},
              'avg_seconds': round(sum(v['seconds']) / len(v['seconds']), 1)} for c, v in summary.items()]
    return res, table


# ── five languages ────────────────────────────────────────────────────────────
FAQ = os.path.join(ROOT, 'rag', 'faq_index.jsonl')
LANGS = ['Arabic-Egyptian', 'Arabic', 'English', 'French', 'Russian']
def family(lang): return 'Arabic' if lang.startswith('Arabic') else lang

def run_languages(agent, per_lang=8, out='prototype_languages.csv', show=True):
    """Held-out Gold questions (test split), the same number per language.
    retrieval_ok: the gold document reached the LLM · same_language: the reply is in the caller's
    language (Egyptian and MSA count as Arabic) · facts: numbers of the gold answer found in the reply."""
    import json
    P = import_module('app.rag.prompt')
    rows = [json.loads(l) for l in open(FAQ, encoding='utf-8')]
    pick = []
    for L in LANGS:
        pool = [q for q in rows if q['split'] == 'test' and q['language'] == L]
        step = max(len(pool) // per_lang, 1)
        pick += pool[::step][:per_lang]                       # spread over intents, deterministic
    res = []
    for k, q in enumerate(pick, 1):
        agent.reset(); r = agent.ask(q['query'])
        res.append({'language': q['language'], 'question': q['query'], 'answer': r['answer'],
                    'gold_answer': q['gold_answer'], 'gold_doc': q['gold_doc_id'], 'docs_given': ' '.join(r['docs']),
                    'retrieval_ok': q['gold_doc_id'] in r['docs'],
                    'same_language': family(P.detect_language(r['answer'])) == family(q['language']),
                    'facts': facts_score(q['gold_answer'], r['answer']), 'seconds': r['seconds']})
        if show: print(f"[{k}/{len(pick)}] ({q['language']}) {q['query']}\n   → {r['answer'][:150]}")
    with open(out, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(res[0].keys())); w.writeheader(); w.writerows(res)
    table = []
    for L in LANGS:
        xs = [x for x in res if x['language'] == L]
        f = [x['facts'] for x in xs if x['facts'] is not None]
        table.append({'language': L, 'n': len(xs),
                      'retrieval_ok': round(sum(x['retrieval_ok'] for x in xs) / len(xs), 2),
                      'same_language': round(sum(x['same_language'] for x in xs) / len(xs), 2),
                      'facts': round(sum(f) / len(f), 2) if f else '-',
                      'avg_seconds': round(sum(x['seconds'] for x in xs) / len(xs), 1)})
    return res, table
