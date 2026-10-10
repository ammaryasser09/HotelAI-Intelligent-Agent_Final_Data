# -*- coding: utf-8 -*-
import math
from collections import Counter
from .text import tokens

class BM25:
    def __init__(self, texts, k1=1.5, b=0.75):
        self.docs = [tokens(t) for t in texts]
        self.k1, self.b = k1, b
        self.avg = sum(map(len, self.docs)) / max(len(self.docs), 1)
        df = Counter(w for d in self.docs for w in set(d)); n = len(self.docs)
        self.idf = {w: math.log(1 + (n - c + .5) / (c + .5)) for w, c in df.items()}
        self.tf = [Counter(d) for d in self.docs]

    def scores(self, query):
        q = tokens(query); out = []
        for tf, d in zip(self.tf, self.docs):
            s = 0.0
            for w in q:
                f = tf.get(w)
                if f:
                    s += self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * len(d) / self.avg))
            out.append(s)
        return out
