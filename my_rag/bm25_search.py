import re                                                 
from rank_bm25 import BM25Okapi                            
from my_rag.config import KB_DIR, BM25_K1, BM25_B, TOP_K 


def tokenize(text):                                       
    return re.findall(r"[a-z0-9]+", text.lower())          


def _load_docs():                                          
    names = []                                             
    corpus = []                                           
    for path in sorted(KB_DIR.glob("*.txt")):              
        names.append(path.name)                            
        corpus.append(tokenize(path.read_text(encoding="utf-8")))  
    return names, corpus                                  


_names, _corpus = _load_docs()                          
_bm25 = BM25Okapi(_corpus, k1=BM25_K1, b=BM25_B)          


def bm25_search(question, top_k=TOP_K):                   
    scores = _bm25.get_scores(tokenize(question))          
    results = []                                          
    for i in range(len(_names)):                          
        results.append((round(float(scores[i]), 2), _names[i]))  
    results.sort(reverse=True)                             
    return results[:top_k]                                 


if __name__ == "__main__":                                 
    for q in ["What time is breakfast?", "How much is the spa?"]:  
        print(q, bm25_search(q))                         