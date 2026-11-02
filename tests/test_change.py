from tests.test_auth import bearer
from tests.test_bookings import book, made, token  # noqa: F401  (pytest fixtures)
from tests.test_expiry import code_uses


def quote(client, token, booking_id, **change):
    return client.get(f"/me/bookings/{booking_id}/change", headers=bearer(token), params=change)


def change(client, token, booking_id, **change):
    return client.post(f"/me/bookings/{booking_id}/change", headers=bearer(token), json=change)


def test_extra_nights_keep_the_room_and_the_price(client, token, made):
    booking = book(client, token, made).json()                      # Double, 2027-11-10 to 13, 8,000 a night

    preview = quote(client, token, booking["booking_id"], check_out="2027-11-15")
    assert preview.status_code == 200, preview.text
    done = change(client, token, booking["booking_id"], check_out="2027-11-15")
    assert done.status_code == 200, done.text
    assert done.json() | {"payment_url": None} == preview.json()   # the quote said exactly what happened

    after = done.json()
    assert after["room_number"] == booking["room_number"] and after["nights"] == 5
    assert (after["total_amount"], after["amount_due"], after["pay_now"]) == (40000, 40000, 8000)
    assert after["booking_status"] == "Pending" and "/payments/mock/" in after["payment_url"]


def test_seven_nights_get_the_long_stay_discount(client, token, made):
    booking_id = book(client, token, made).json()["booking_id"]
    after = change(client, token, booking_id, check_out="2027-11-17").json()
    assert after["discount"] == {"source": "Long Stay", "code": None, "amount": 6720}   # 56,000 x 12%
    assert after["amount_due"] == 49280


def test_long_stay_beats_the_code_so_the_code_is_given_back(client, token, made):
    before = code_uses("PEARL500")
    booking_id = book(client, token, made, code="PEARL500").json()["booking_id"]
    made[-1] = (booking_id, None)                                    # the change un-counts the code itself
    after = change(client, token, booking_id, check_out="2027-11-17").json()
    assert after["discount"]["source"] == "Long Stay"
    assert code_uses("PEARL500") == before


def test_cheaper_stay_after_paying_gives_the_difference_back(client, token, made):
    booking_id = book(client, token, made).json()["booking_id"]
    client.post(f"/payments/mock/{booking_id}/pay")                  # deposit 8,000 paid: Confirmed

    after = change(client, token, booking_id, room_type="Single", check_out="2027-11-11", adults=1).json()
    assert after["room_type"] == "Single" and after["price_per_night"] == 6000     # the new type's own price
    assert (after["amount_due"], after["refund"], after["amount_paid"], after["pay_at_hotel"]) == (6000, 2000, 6000, 0)
    assert after["booking_status"] == "Confirmed" and after["payment_url"] is None

    mine = {b["booking_id"]: b for b in client.get("/me/bookings", headers=bearer(token)).json()}[booking_id]
    assert (mine["payment_status"], mine["refund_amount"]) == ("Partially Refunded", 2000)


def test_changes_that_are_refused(client, token, made):
    booking_id = book(client, token, made).json()["booking_id"]
    reasons = {
        "NOTHING_TO_CHANGE": change(client, token, booking_id, check_out="2027-11-13"),
        "CHECK_OUT_NOT_AFTER_CHECK_IN": change(client, token, booking_id, check_out="2027-11-09"),
        "CAPACITY_EXCEEDED": change(client, token, booking_id, adults=3),
        "UNKNOWN_ROOM_TYPE": change(client, token, booking_id, room_type="Castle"),
    }
    for reason, response in reasons.items():
        assert response.json()["detail"]["reason"] == reason, response.text

    non_refundable = book(client, token, made, rate_plan="Non-refundable").json()["booking_id"]
    assert change(client, token, non_refundable, check_out="2027-11-14").json()["detail"]["reason"] == "NON_REFUNDABLE_CANNOT_CHANGE"
    assert change(client, token, "B000001", check_out="2027-07-25").status_code == 404      # another guest's
