# -*- coding: utf-8 -*-
"""Paths and retrieval settings. Everything is relative to the project root."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORPUS = os.path.join(ROOT, 'rag', 'corpus.jsonl')                    # knowledge-base chunks
FAQ = os.path.join(ROOT, 'rag', 'faq_index.jsonl')                    # answered questions + split (scripts/build_rag.py)
OPS = os.path.join(ROOT, 'database', 'seed')                          # database tables (the seed CSVs)
import csv as _csv
from datetime import date as _date
# "Today" of the demo data: app_settings.system_date (also hotel_today() in PostgreSQL)
SYSTEM_DATE = _date.fromisoformat(next(r['value'] for r in _csv.DictReader(open(os.path.join(OPS, 'app_settings.csv'), encoding='utf-8')) if r['key'] == 'system_date'))
INDEX_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index')

DENSE_MODEL = 'BAAI/bge-m3'     # multilingual: Arabic, Egyptian, English, French, Russian
TOP_DOCS = 3                    # documents passed to the LLM
CHUNKS_PER_DOC = 2              # best chunks taken from each document
FAQ_EXAMPLES = 3                # similar answered questions shown to the LLM
RRF_K = 60                      # reciprocal-rank-fusion constant

AGENT_NAME = {'ar': 'نور', 'en': 'Nour', 'fr': 'Nour', 'ru': 'Нур'}   # the agent's name (female voice)
