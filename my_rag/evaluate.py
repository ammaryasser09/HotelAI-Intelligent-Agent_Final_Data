import csv
import time
from my_rag.config import ROOT, FAQ_FILE
from my_rag import search as s

TEST_FILE = ROOT / "evaluation" / "realistic_test_egyptian.csv"


def load_tests():
    positives = []
    refuse = []
    with open(TEST_FILE, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if "RAG" in row["route"].split("+") and row["expected_doc"].strip():
                positives.append({"question": row["question"], "docs": row["expected_doc"].split(";")})
            elif row["route"] == "REFUSE":
                refuse.append(row["question"])
    faq_out = []
    with open(FAQ_FILE, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["source_doc"] == "out_of_scope_policy" and row["split"] != "train":
                faq_out.append(row["question"])
    return positives, refuse, faq_out


def evaluate_answers(positives):
    at5 = 0
    at20 = 0
    times = []
    misses = []
    for item in positives:
        start = time.time()
        results = s.search(item["question"])
        times.append(time.time() - start)
        best, dense = s.hybrid_rank(item["question"])
        top5 = []
        for r in results:
            top5.append(r["source"])
        top20 = []
        for i in best:
            top20.append(s._chunks[i]["source"])
        if any(d in top5 for d in item["docs"]):
            at5 += 1
        else:
            misses.append((item["question"], item["docs"], top5[:3]))
        if any(d in top20 for d in item["docs"]):
            at20 += 1
    n = len(positives)
    return {
        "recall_at_5": round(100 * at5 / n),
        "recall_at_20": round(100 * at20 / n),
        "avg_time": round(sum(times) / n, 3),
        "max_time": round(max(times), 3),
        "misses": misses,
    }


def evaluate_outside(questions):
    blocked = 0
    for q in questions:
        if s.search(q) == []:
            blocked += 1
    return blocked


if __name__ == "__main__":
    positives, refuse, faq_out = load_tests()
    print(len(positives), "with answer |", len(refuse), "refuse |", len(faq_out), "faq outside")
    r = evaluate_answers(positives)
    print("Recall@5 :", r["recall_at_5"], "%")
    print("Recall@20:", r["recall_at_20"], "%")
    print("time: avg", r["avg_time"], "s | max", r["max_time"], "s")
    print("outside blocked: refuse", evaluate_outside(refuse), "/", len(refuse),
          "| faq", evaluate_outside(faq_out), "/", len(faq_out))
    print()
    print("misses:")
    for q, docs, got in r["misses"]:
        print("   ", q, "| expected:", docs, "| got:", got)