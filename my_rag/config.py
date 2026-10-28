from pathlib import Path                                   

ROOT = Path(__file__).resolve().parent.parent           
KB_DIR = ROOT / "knowledge_base"                         

BM25_K1 = 1.5                                            
BM25_B = 0.75                                              
TOP_K = 3                                                


MODELS_DIR = ROOT / "models"                              
DENSE_MODEL = "BAAI/bge-m3"                              
DENSE_BATCH_SIZE = 4                                      
DENSE_MAX_LENGTH = 512       

FAQ_FILE = ROOT / "rag" / "hotel_faq_gold.csv"
INDEX_DIR = ROOT / "my_rag" / "index"
CHUNKS_FILE = INDEX_DIR / "chunks.jsonl"
VECTORS_FILE = INDEX_DIR / "vectors.npy"

SEARCH_TOP_K = 5
RETRIEVE_N = 20
RRF_K = 60
BM25_WEIGHT = 0.0