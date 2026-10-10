# -*- coding: utf-8 -*-
"""
Dense embeddings with an on-disk cache.

  Embedder('BAAI/bge-m3')   the real multilingual model (pip install sentence-transformers)
  Embedder('hashing')       offline smoke test only: character n-grams, no cross-lingual
                            ability. It exists so the code path can be tested without a
                            download; never report its numbers as the model's quality.
"""
import hashlib, os
import numpy as np
from .config import INDEX_DIR

class Embedder:
    def __init__(self, name):
        self.name = name
        if name == 'hashing':
            from sklearn.feature_extraction.text import HashingVectorizer
            self._hv = HashingVectorizer(analyzer='char_wb', ngram_range=(2, 4), n_features=2 ** 18,
                                         alternate_sign=False, norm='l2')
        else:
            from sentence_transformers import SentenceTransformer
            self._m = SentenceTransformer(name)

    def encode(self, texts, batch_size=32):
        if self.name == 'hashing':
            return self._hv.transform(texts)                       # sparse, L2-normalised
        return self._m.encode(texts, batch_size=batch_size, normalize_embeddings=True,
                              show_progress_bar=len(texts) > 200)

    def encode_cached(self, texts, tag):
        """Embeddings for a fixed text list, reused while the texts are unchanged."""
        if self.name == 'hashing':
            return self.encode(texts)
        h = hashlib.sha1(('\n'.join(texts) + self.name).encode('utf-8')).hexdigest()[:12]
        os.makedirs(INDEX_DIR, exist_ok=True)
        p = os.path.join(INDEX_DIR, f'{tag}_{self.name.replace("/", "_")}_{h}.npy')
        if os.path.exists(p):
            return np.load(p)
        v = self.encode(texts); np.save(p, v); return v

def cosine(query_vec, matrix):
    """Scores of one query against a matrix of normalised vectors (dense or sparse)."""
    s = matrix @ query_vec.T
    s = s.toarray().ravel() if hasattr(s, 'toarray') else np.asarray(s).ravel()
    return s
