import torch                                                     
from sentence_transformers import SentenceTransformer           
from my_rag.config import (                                      
    KB_DIR, MODELS_DIR, DENSE_MODEL, DENSE_BATCH_SIZE, DENSE_MAX_LENGTH, TOP_K,
)


def _pick_device():                                              
    if torch.cuda.is_available():                               
        return "cuda"
    if torch.backends.mps.is_available():                      
        return "mps"
    return "cpu"                                                


def _load_model():                                              
    device = _pick_device()                                      
    model = SentenceTransformer(DENSE_MODEL, cache_folder=str(MODELS_DIR), device=device)  
    if device != "cpu":                                         
        model.half()                                             
    model.max_seq_length = DENSE_MAX_LENGTH                      
    return model


def _load_docs():                                             
    names = []                                                   
    texts = []                                                 
    for path in sorted(KB_DIR.glob("*.txt")):                    
        names.append(path.name)                                 
        texts.append(path.read_text(encoding="utf-8"))           
    return names, texts


_model = _load_model()                                          
_names, _texts = _load_docs()                                   
_doc_vecs = _model.encode(_texts, normalize_embeddings=True, batch_size=DENSE_BATCH_SIZE) 


def dense_search(question, top_k=TOP_K):                         
    q_vec = _model.encode([question], normalize_embeddings=True) 
    scores = _model.similarity(q_vec, _doc_vecs)[0]             
    results = []                                                
    for i in range(len(_names)):                                
        results.append((round(float(scores[i]), 2), _names[i]))  
    results.sort(reverse=True)                                  
    return results[:top_k]                                  


if __name__ == "__main__":                                      
    while True:                                             
        q = input("Question (Enter to stop): ").strip()         
        if not q:                                                
            break                                               
        for score, name in dense_search(q):                      
            print("   ", score, name)                            
        print()                                                  