from my_rag.search import search


def search_hotel_info(question):
    results = search(question, top_k=5)
    if not results:
        return {"ok": True, "found": False}
    return {
        "ok": True,
        "found": True,
        "results": [{"text": r["text"], "source": r["source"]} for r in results],
    }