from pathlib import Path                                   

ROOT = Path(__file__).resolve().parent.parent           
KB_DIR = ROOT / "knowledge_base"                         

BM25_K1 = 1.5                                            
BM25_B = 0.75                                              
TOP_K = 3                                                


MODELS_DIR = ROOT / "models"                               # فولدر الموديلات
DENSE_MODEL = "BAAI/bge-m3"                                # اسم موديل الـ Embeddings
DENSE_BATCH_SIZE = 4                                       # كام ملف يتحوّل في المرة (قليل عشان الأجهزة اللي رامها قليلة)
DENSE_MAX_LENGTH = 512                                     # أقصى طول للنص بالـ token