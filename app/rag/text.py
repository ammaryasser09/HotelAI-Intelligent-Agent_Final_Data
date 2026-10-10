# -*- coding: utf-8 -*-
"""Tokenisation with Arabic normalisation, so Egyptian and MSA spellings meet in BM25."""
import re

_DIAC = re.compile(r'[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u0640]')   # tashkeel + tatweel
_TOK = re.compile(r'[\w\u0600-\u06ff]+', re.U)
_MAP = str.maketrans({'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا', 'ى': 'ي', 'ة': 'ه', 'ؤ': 'و', 'ئ': 'ي'})

def normalize(text: str) -> str:
    return _DIAC.sub('', text).translate(_MAP).lower()

def tokens(text: str) -> list:
    return _TOK.findall(normalize(text))
