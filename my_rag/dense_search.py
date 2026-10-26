import torch                                                     # عشان نعرف الجهاز فيه كارت شاشة ولا لأ
from sentence_transformers import SentenceTransformer            # المكتبة اللي بتشغّل BGE-M3
from my_rag.config import (                                      # الإعدادات من config.py
    KB_DIR, MODELS_DIR, DENSE_MODEL, DENSE_BATCH_SIZE, DENSE_MAX_LENGTH, TOP_K,
)


def _pick_device():                                              # بتختار الجهاز لوحدها، فنفس الكود يشتغل على الويندوز والماك
    if torch.cuda.is_available():                                # لو فيه كارت NVIDIA
        return "cuda"
    if torch.backends.mps.is_available():                        # لو ماك Apple Silicon
        return "mps"
    return "cpu"                                                 # غير كده نشتغل على الـ CPU


def _load_model():                                               # بتحمّل الموديل وتظبطه
    device = _pick_device()                                      # نختار الجهاز
    model = SentenceTransformer(DENSE_MODEL, cache_folder=str(MODELS_DIR), device=device)  # نحمّل BGE-M3 من فولدر models
    if device != "cpu":                                          # على كارت الشاشة بس
        model.half()                                             # نص الذاكرة (على الـ CPU بيبطّأ، فمش بنعمله هناك)
    model.max_seq_length = DENSE_MAX_LENGTH                      # أقصى طول للنص
    return model


def _load_docs():                                                # بتقرا ملفات الفندق
    names = []                                                   # أسماء الملفات بالترتيب
    texts = []                                                   # الكلام اللي فيهم، بنفس الترتيب
    for path in sorted(KB_DIR.glob("*.txt")):                    # نلف على كل ملفات الـ txt بالترتيب الأبجدي
        names.append(path.name)                                  # نحفظ اسم الملف
        texts.append(path.read_text(encoding="utf-8"))           # ونحفظ الكلام اللي فيه
    return names, texts


_model = _load_model()                                           # الموديل بيتحمّل مرة واحدة أول ما الملف يتعمله import
_names, _texts = _load_docs()                                    # والملفات بتتقري مرة واحدة
_doc_vecs = _model.encode(_texts, normalize_embeddings=True, batch_size=DENSE_BATCH_SIZE)  # والملفات بتتحوّل لأرقام مرة واحدة


def dense_search(question, top_k=TOP_K):                         # الدالة اللي الباقي هيستخدمها
    q_vec = _model.encode([question], normalize_embeddings=True) # السؤال بيتحوّل لـ 1024 رقم
    scores = _model.similarity(q_vec, _doc_vecs)[0]              # الـ cosine بين السؤال وكل ملف
    results = []                                                 # هنحط فيها (الـ score، اسم الملف)
    for i in range(len(_names)):                                 # نلف على كل الملفات
        results.append((round(float(scores[i]), 2), _names[i]))  # float بتحوّله لرقم بايثون عادي
    results.sort(reverse=True)                                   # نرتّب من الأعلى للأقل
    return results[:top_k]                                       # نرجّع أعلى top_k ملفات


if __name__ == "__main__":                                       # بيشتغل بس لو شغّلنا الملف ده لوحده
    while True:                                                  # نفضل نسأل لحد ما نوقف
        q = input("Question (Enter to stop): ").strip()          # ناخد السؤال من الكيبورد
        if not q:                                                # لو دوستي Enter من غير كلام
            break                                                # نوقف
        for score, name in dense_search(q):                      # ندوّر ونلف على النتايج
            print("   ", score, name)                            # نطبع الـ score واسم الملف
        print()                                                  # سطر فاضي بين الأسئلة