# -*- coding: utf-8 -*-
"""
Hybrid retrieval over two indexes:

  KB index   the chunks of knowledge_base/ (English, rag/corpus.jsonl) — the facts the answer uses
  FAQ index  answered guest questions from the Gold FAQ *train* split, in all five languages.
             An Arabic or Egyptian question meets an Arabic or Egyptian FAQ question, and the
             FAQ row points at its source document. This is the cross-lingual bridge the
             English-only KB lacks.

Each index is searched lexically (BM25 with Arabic normalisation) and, when a dense model is
available, semantically (BGE-M3). The four document rankings are fused with reciprocal-rank
fusion. The pseudo-document 'out_of_scope_policy' can win: it tells the agent to decline.
"""
import json
from collections import defaultdict
from .bm25 import BM25
from .config import CORPUS, FAQ, TOP_DOCS, CHUNKS_PER_DOC, FAQ_EXAMPLES, RRF_K, DENSE_MODEL
from .embedder import Embedder, cosine

OUT_OF_SCOPE = 'out_of_scope_policy'

def _load(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]

class HybridRetriever:
    def __init__(self, mode='hybrid', embedder=DENSE_MODEL, use_faq=True, faq_splits=('train',)):
        assert mode in ('bm25', 'dense', 'hybrid')
        self.mode, self.use_faq = mode, use_faq
        self.chunks = _load(CORPUS)
        self.faq = [q for q in _load(FAQ) if q['split'] in faq_splits] if use_faq else []
        self.docs = sorted({c['doc_id'] for c in self.chunks}) + [OUT_OF_SCOPE]
        if mode in ('bm25', 'hybrid'):
            self.kb_bm25 = BM25([c['text'] for c in self.chunks])
            self.faq_bm25 = BM25([q['query'] for q in self.faq]) if self.faq else None
        if mode in ('dense', 'hybrid'):
            self.emb = embedder if isinstance(embedder, Embedder) else Embedder(embedder)
            self.kb_vec = self.emb.encode_cached([c['text'] for c in self.chunks], 'kb')
            self.faq_vec = self.emb.encode_cached([q['query'] for q in self.faq], 'faq') if self.faq else None

    # ── scoring ──
    def _channels(self, query):
        """{channel: (item scores, kind)}; kind 'kb' scores chunks, 'faq' scores FAQ rows."""
        ch = {}
        if self.mode in ('bm25', 'hybrid'):
            ch['kb_bm25'] = (self.kb_bm25.scores(query), 'kb')
            if self.faq: ch['faq_bm25'] = (self.faq_bm25.scores(query), 'faq')
        if self.mode in ('dense', 'hybrid'):
            qv = self.emb.encode([query])
            qv = qv if hasattr(qv, 'toarray') else qv[0]
            ch['kb_dense'] = (cosine(qv, self.kb_vec), 'kb')
            if self.faq: ch['faq_dense'] = (cosine(qv, self.faq_vec), 'faq')
        return ch

    def _doc_of(self, kind, i):
        return self.chunks[i]['doc_id'] if kind == 'kb' else self.faq[i]['gold_doc_id']

    def search(self, query, top_docs=TOP_DOCS):
        ch = self._channels(query)
        doc_rrf, chunk_rrf, faq_rrf = defaultdict(float), defaultdict(float), defaultdict(float)
        for name, (scores, kind) in ch.items():
            order = [i for i in sorted(range(len(scores)), key=lambda i: -scores[i]) if scores[i] > 0]
            seen = []
            for i in order:                                    # document ranking of this channel
                d = self._doc_of(kind, i)
                if d not in seen: seen.append(d)
            for r, d in enumerate(seen): doc_rrf[d] += 1 / (RRF_K + r + 1)
            for r, i in enumerate(order[:200]):
                (chunk_rrf if kind == 'kb' else faq_rrf)[i] += 1 / (RRF_K + r + 1)
        ranked = sorted(doc_rrf, key=lambda d: -doc_rrf[d])
        top = ranked[:top_docs]
        chunks = []
        for d in top:
            if d == OUT_OF_SCOPE: continue
            cs = sorted((i for i, c in enumerate(self.chunks) if c['doc_id'] == d), key=lambda i: -chunk_rrf.get(i, 0))
            chunks += [self.chunks[i] for i in cs[:CHUNKS_PER_DOC]]
        examples = [self.faq[i] for i in sorted(faq_rrf, key=lambda i: -faq_rrf[i])[:FAQ_EXAMPLES]]
        return {'ranked_docs': ranked, 'docs': top, 'chunks': chunks, 'faq_examples': examples,
                'out_of_scope': bool(top) and top[0] == OUT_OF_SCOPE}
