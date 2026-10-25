from pathlib import Path                                   

ROOT = Path(__file__).resolve().parent.parent           
KB_DIR = ROOT / "knowledge_base"                         

BM25_K1 = 1.5                                            
BM25_B = 0.75                                              
TOP_K = 3                                                