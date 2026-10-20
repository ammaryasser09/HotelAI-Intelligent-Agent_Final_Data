def test_room_types(client):
    types = client.get("/room-types").json()
    assert len(types) == 6
    prices = [t["base_price"] for t in types]
    assert prices == sorted(prices)
    suite = next(t for t in types if t["room_type_name"] == "Suite")
    assert suite["image_city"] is None


def test_hotel_photos(client):
    photos = client.get("/hotel-photos").json()
    assert len(photos) >= 1
    assert all(p["image_path"].startswith("/static/hotel/") for p in photos)

    pool = client.get("/hotel-photos", params={"photo_key": "pool"}).json()
    assert [p["photo_key"] for p in pool] == ["pool"]

    missing = client.get("/hotel-photos", params={"photo_key": "rooftop-bar"})
    assert missing.status_code == 404
    assert missing.json()["detail"]["reason"] == "PHOTO_NOT_FOUND"


def test_menu(client):
    full = client.get("/menu").json()
    night = client.get("/menu", params={"night_only": True}).json()
    drinks = client.get("/menu", params={"category": "drinks"}).json()
    assert full["delivery_charge"] == 300
    assert 0 < len(night["items"]) < len(full["items"])
    assert drinks["items"] and all(i["category"] == "Drinks" for i in drinks["items"])


def test_discount_codes(client):
    ok = client.get("/discount-codes/pearl100").json()
    assert ok["usable"] is True and ok["code"] == "PEARL100"

    assert client.get("/discount-codes/PEARL750").json()["reason"] == "CODE_NOT_ACTIVE"   # Exhausted
    assert client.get("/discount-codes/PEARL888").json()["reason"] == "CODE_NOT_ACTIVE"   # Scheduled
    assert client.get("/discount-codes/PEARL707").json()["reason"] == "CODE_NOT_ACTIVE"   # Expired

    personal = client.get("/discount-codes/PEARL6290").json()
    assert personal["usable"] is False and personal["reason"] == "PERSONAL_CODE_LOGIN_REQUIRED"
    assert personal["discount_value"] is None   # nothing else is shown about another guest's code

    assert client.get("/discount-codes/NOPE123").status_code == 404


def availability(client, **params):
    base = {"room_type": "Suite", "check_in": "2026-10-03", "check_out": "2026-10-06", "guests": 2}
    return client.get("/availability", params={**base, **params}).json()


def test_availability_with_codes(client):
    # 3 nights x 20,000 = 60,000; PEARL100 is 10% -> 6,000
    body = availability(client, discount_code="PEARL100")
    assert body["flexible"]["discount"] == {"source": "Code", "code": "PEARL100", "amount": 6000}
    assert body["flexible"]["amount_due"] == 54000
    assert body["non_refundable"]["total"] == 51000          # no code on Non-refundable

    # PEARL500 is a fixed 1,500 EGP
    assert availability(client, discount_code="PEARL500")["flexible"]["discount"]["amount"] == 1500

    # 10 nights: Long Stay 24,000 is bigger than the code's 20,000
    body = availability(client, check_in="2026-11-01", check_out="2026-11-11", discount_code="PEARL100")
    assert body["flexible"]["discount"]["source"] == "Long Stay"

    # a code that cannot be used: no discount, and the reason is returned
    body = availability(client, discount_code="PEARL750")
    assert body["flexible"]["discount"] is None
    assert body["discount_code_not_used"] == "CODE_NOT_ACTIVE"
    assert availability(client, discount_code="NOPE123")["discount_code_not_used"] == "CODE_NOT_FOUND"
