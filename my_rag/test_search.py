import time
import pytest
from my_rag.search import search

QUESTIONS = [
    ("الشيك إن الساعة كام؟", ["check_in_check_out.txt"]),
    ("الفطار بكام للطفل؟", ["breakfast.txt"]),
    ("ودي أعرف عندكم مسبح؟ ومتى يفتح؟", ["hotel_facilities.txt"]),
    ("هل يُسمح باصطحاب الحيوانات الأليفة؟", ["pet_policy.txt", "hotel_information.txt"]),
    ("How far is the airport and do you offer pickup?", ["airport_transfer.txt"]),
    ("Can I cancel my booking and get my deposit back?", ["cancellation_policy.txt", "refund_policy.txt"]),
    ("À quelle heure est le petit-déjeuner ?", ["breakfast.txt"]),
    ("Есть ли у вас спа?", ["spa.txt"]),
    ("مين كسب ماتش الأهلي امبارح؟", []),
    ("Recommend me a good movie to watch tonight", []),
]


def test_returns_list_of_dicts():
    results = search("الشيك إن الساعة كام؟")
    assert isinstance(results, list)
    assert len(results) > 0
    for r in results:
        assert set(r.keys()) == {"text", "source", "score"}
        assert isinstance(r["text"], str)
        assert isinstance(r["source"], str)
        assert isinstance(r["score"], float)


def test_top_k():
    assert len(search("الشيك إن الساعة كام؟", top_k=1)) <= 1
    assert len(search("الشيك إن الساعة كام؟", top_k=3)) <= 3


def test_bad_input_returns_empty():
    assert search("") == []
    assert search("   ") == []
    assert search(None) == []


@pytest.mark.parametrize("question, expected", QUESTIONS)
def test_question(question, expected):
    results = search(question)
    sources = []
    for r in results:
        sources.append(r["source"])
    if not expected:
        assert results == [], sources
    else:
        assert any(d in sources for d in expected), sources


def test_speed():
    start = time.time()
    for question, expected in QUESTIONS:
        search(question)
    avg = (time.time() - start) / len(QUESTIONS)
    assert avg < 0.5, avg