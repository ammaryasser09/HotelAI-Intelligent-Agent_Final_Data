import csv
from pathlib import Path

import pytest

CASES_FILE = Path(__file__).resolve().parents[1] / "database" / "tests" / "availability_cases.csv"

# AV06 checks the database rule "a No-show does not block its room" on a date in the past.
# Through the API a past check-in is refused before any room is looked at, so the API answer is
# CHECK_IN_IN_THE_PAST. The rule itself is checked in database/tests/run_checks.sql.
API_EXPECTED_ERROR = {"AV06": "CHECK_IN_IN_THE_PAST"}

# Refused by Pydantic (422) before the endpoint runs, so there is no "reason" in the answer
VALIDATION_ERRORS = {"CHECK_OUT_NOT_AFTER_CHECK_IN"}


def load_cases():
    with CASES_FILE.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.mark.parametrize("case", load_cases(), ids=lambda case: case["case_id"])
def test_availability_case(client, case):
    response = client.get("/availability", params={
        "room_type": case["room_type"],
        "check_in": case["check_in"],
        "check_out": case["check_out"],
        "guests": case["guests"],
    })
    expected_error = API_EXPECTED_ERROR.get(case["case_id"], case["expected_error"])

    if expected_error in VALIDATION_ERRORS:
        assert response.status_code == 422, response.text
        return

    if expected_error:
        assert response.status_code in (400, 404), response.text
        assert response.json()["detail"]["reason"] == expected_error
        return

    assert response.status_code == 200, response.text
    body = response.json()
    if case["expected_free_count"]:
        assert body["rooms_free"] == int(case["expected_free_count"])
    if case["must_include"]:
        assert int(case["must_include"]) in body["free_room_numbers"]
    if case["must_exclude"]:
        assert int(case["must_exclude"]) not in body["free_room_numbers"]


def test_no_free_rooms_offers_alternatives(client):
    body = client.get("/availability", params={
        "room_type": "Double", "check_in": "2026-12-24", "check_out": "2026-12-27", "guests": 2,
    }).json()
    assert body["rooms_free"] == 0
    for alternative in body["alternatives"]:
        assert alternative["room_type"] != "Double"
        assert alternative["capacity"] >= 2
        assert alternative["rooms_free"] > 0
