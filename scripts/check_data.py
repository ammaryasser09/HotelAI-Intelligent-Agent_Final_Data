#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check the data after any edit (knowledge base, FAQ, prices):

    python scripts/check_data.py          # exit code 0 = every check passed

  - the RAG files are rebuilt from the current knowledge base and FAQ (else: run build_rag.py)
  - every FAQ answer cites a knowledge-base document (or the out-of-scope policy)
  - every number in every answer exists in the knowledge base or the price tables
  - the same fact quotes the same numbers in English, Arabic, French and Russian (fact_id)
  - every Egyptian reply quotes the same amounts as its Modern Standard Arabic answer
  - no answer keeps old "not specified" wording for a rule the knowledge base now states
  - room prices in the knowledge base equal database/seed/room_types.csv
The database has its own checks: database/tests/run_checks.sql.
"""
import csv, glob, os, re, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_rag as B

ROOT = B.ROOT
SEED = os.path.join(ROOT, 'database', 'seed')
PRICE_TABLES = ('room_types', 'services', 'fees', 'menu_items', 'loyalty_tiers', 'loyalty_rules', 'pricing_tiers')
AR = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
SMALL = {str(i) for i in range(0, 32)} | {'35', '45', '50', '60', '100'}
STALE = re.compile(r"seven steps|sept étapes|سبع خطوات|does not publish a universal|does not provide the complete loyalty|"
                   r"не устанавливает единый|may offer a loyalty program|مهلة موحدة|لا يوجد وقت محدد", re.I)
results = []
def check(name, ok, detail=''):
    results.append(ok); print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f'  - {detail}' if detail and not ok else ''))

def nums(s):
    """Numbers in a text; times on a 12-hour clock (15:00 = 3, French 15h, 10h30); '24/7' is not a time."""
    s = s.translate(AR)
    s = re.sub(r'24\s?h\s?/\s?24|24/7|7\s?j\s?/\s?7|7 jours sur 7|7 дней в неделю|24 heures sur 24|24 часа в сутки', ' ', s)
    s = re.sub(r'\b(\d{1,2})\s?h\s?(\d{2})\b', r'\1:\2', s)
    s = re.sub(r'\b(\d{1,2})\s?h\b', r'\1:00', s)
    s = re.sub(r'\bB\d{6}\b|\+?20 ?2 ?2794 ?55\d\d|\b20[12]\d\b', ' ', s)
    s = re.sub(r'(?<=\d)[,   ](?=\d{3}\b)', '', s)
    out = set()
    for m in re.findall(r'\d+(?:[.:]\d+)?', s):
        if ':' in m:
            h, mi = m.split(':'); h = int(h or 0); h = h - 12 if h > 12 else h
            out.add(f'{h}' if mi in ('00', '0') else f'{h}:{mi}')
        else:
            out.add(re.sub(r'\.0+$', '', m).lstrip('0') or '0')
    return out

gold = list(csv.DictReader(open(B.GOLD, encoding='utf-8')))
kb_files = {os.path.basename(f) for f in glob.glob(os.path.join(B.KB, '*.txt'))}
print('[1] RAG files')
check('rag/corpus.jsonl matches the knowledge base', open(B.CORPUS, encoding='utf-8').read() == B.dump(B.corpus_chunks()),
      'run: python scripts/build_rag.py')
check('rag/faq_index.jsonl matches hotel_faq_gold.csv', open(B.FAQ, encoding='utf-8').read() == B.dump(B.faq_rows()),
      'run: python scripts/build_rag.py')
print('[2] FAQ')
check('faq_id is unique', len({r['faq_id'] for r in gold}) == len(gold))
bad = [r['faq_id'] for r in gold if r['source_doc'] not in kb_files and r['source_doc'] != 'out_of_scope_policy']
check('every answer cites a knowledge-base document', not bad, f'{bad[:5]}')
check('split is train, val or test', all(r['split'] in ('train', 'val', 'test') for r in gold))
known = nums(''.join(open(os.path.join(B.KB, f), encoding='utf-8').read() for f in kb_files)) | SMALL
for t in PRICE_TABLES: known |= nums(open(os.path.join(SEED, f'{t}.csv'), encoding='utf-8').read())
unknown = sorted({(r['faq_id'], n) for r in gold for col in ('answer', 'answer_egyptian') for n in nums(r[col]) - known})
check('every number in every answer exists in the knowledge base or the price tables', not unknown, f'{unknown[:5]}')
facts = defaultdict(dict)
for r in gold:
    if r['fact_id'] and r['language'] != 'Arabic-Egyptian': facts[r['fact_id']][r['faq_id']] = r
cross = []
for fid, rows in facts.items():
    en = next((r for r in rows.values() if r['language'] == 'English'), None)
    if not en: continue
    e = nums(en['answer']) - {'24'}
    for r in rows.values():
        tr = nums(r['answer']) - {'24'}
        if (tr - e) or {x for x in e - tr if not (x.isdigit() and int(x) <= 5)}: cross.append((en['faq_id'], r['faq_id']))
check(f'the same fact quotes the same numbers in 4 languages ({len(facts)} facts)', not cross, f'{cross[:5]}')
big = lambda s: {x for x in nums(s) if x.isdigit() and int(x) >= 100}
egy = [r['faq_id'] for r in gold if r['language'] == 'Arabic-Egyptian' and big(r['answer']) != big(r['answer_egyptian'])]
check('Egyptian replies quote the same amounts as their MSA answer', not egy, f'{egy[:5]}')
stale = [r['faq_id'] for r in gold if STALE.search(r['answer']) or STALE.search(r['answer_egyptian'])]
check('no old "not specified" wording', not stale, f'{stale[:5]}')
print('[3] Knowledge base vs database')
kbtxt = open(os.path.join(B.KB, 'room_types.txt'), encoding='utf-8').read()
miss = [r['room_type_name'] for r in csv.DictReader(open(os.path.join(SEED, 'room_types.csv'), encoding='utf-8'))
        if f"{int(float(r['base_price'])):,} EGP per night" not in kbtxt]
check('room prices in room_types.txt equal the database', not miss, f'{miss}')
print(f"\nRESULT: {sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
