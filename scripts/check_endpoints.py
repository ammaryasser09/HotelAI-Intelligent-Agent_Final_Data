"""Calls every endpoint of the running API once and prints OK / FAIL for each.

Start the API first (uvicorn app.api.main:app --reload), then from the project root:
    python scripts/check_endpoints.py
It makes one booking for the demo guest Paul and cancels it at the end (it stays in the database as Cancelled).
"""
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
GUEST = {"email": "paul.fischer500@example.com", "password": "NilePearl@2026"}
STAY = {"room_type": "Double", "check_in": "2027-12-10", "check_out": "2027-12-12", "adults": 2}
results = []


def check(name, response, expected=200, test=None):
    ok = response.status_code == expected and (test is None or bool(test(response.json())))
    results.append(ok)
    print(f"{'OK  ' if ok else 'FAIL'}  {response.status_code}  {name}")
    if not ok:
        print("      expected", expected, "->", response.text[:300])
    return response


def first_static_path(data):
    if isinstance(data, str):
        return data if "/static/" in data else None
    items = data.values() if isinstance(data, dict) else data if isinstance(data, list) else []
    for item in items:
        found = first_static_path(item)
        if found:
            return found
    return None


with httpx.Client(base_url=BASE, timeout=30) as api:
    print(f"Checking {BASE}\n--- public")
    check("GET  /", api.get("/"))
    check("GET  /health", api.get("/health"))
    room_types = check("GET  /room-types", api.get("/room-types"), test=lambda j: len(j) == 6)
    check("GET  /hotel-photos", api.get("/hotel-photos"))
    check("GET  /hotel-photos (unknown key -> 404)", api.get("/hotel-photos", params={"photo_key": "castle"}), 404)
    check("GET  /menu", api.get("/menu"))
    check("GET  /availability", api.get("/availability", params={**STAY, "guests": 2}),
          test=lambda j: j["free_room_numbers"])
    check("GET  /availability (check-out before check-in -> 422)",
          api.get("/availability", params={**STAY, "check_out": "2027-12-09"}), 422)
    check("GET  /discount-codes/PEARL500", api.get("/discount-codes/PEARL500"))
    image = first_static_path(room_types.json())
    if image:
        path = "/static/" + image.split("/static/", 1)[1]
        check(f"GET  {path}", api.get(path))

    print("--- login")
    check("POST /auth/login (wrong password -> 401)", api.post("/auth/login", json={**GUEST, "password": "wrong"}), 401)
    token = check("POST /auth/login", api.post("/auth/login", json=GUEST)).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    check("GET  /auth/me", api.get("/auth/me", headers=auth))
    check("GET  /auth/me (no token -> 401)", api.get("/auth/me"), 401)
    check("GET  /me/bookings", api.get("/me/bookings", headers=auth))
    check("POST /me/bookings/link", api.post("/me/bookings/link", headers=auth,
                                             json={"booking_ref": "B011936", "last_name": "Fischer"}))

    print("--- booking cycle")
    booking = check("POST /bookings", api.post("/bookings", headers=auth, json=STAY), 201).json()
    booking_id = booking["booking_id"]
    mock = "/payments/mock/" in booking["payment_url"]
    if mock:
        check("GET  /payments/mock/{id}", api.get(f"/payments/mock/{booking_id}"))
    else:
        print("      (PAYMENT_PROVIDER=paymob: the payment is not made here)")
    check("GET  /me/bookings/{id}/change", api.get(f"/me/bookings/{booking_id}/change", headers=auth,
                                                   params={"check_out": "2027-12-13"}), test=lambda j: j["nights"] == 3)
    check("POST /me/bookings/{id}/change", api.post(f"/me/bookings/{booking_id}/change", headers=auth,
                                                    json={"check_out": "2027-12-13"}), test=lambda j: j["nights"] == 3)
    if mock:
        check("POST /payments/mock/{id}/pay", api.post(f"/payments/mock/{booking_id}/pay"),
              test=lambda j: j["booking_status"] == "Confirmed")
        check("POST /payments/paymob/webhook (mock mode -> 404)", api.post("/payments/paymob/webhook", json={}), 404)
    check("GET  /me/bookings/{id}/cancellation", api.get(f"/me/bookings/{booking_id}/cancellation", headers=auth))
    check("POST /me/bookings/{id}/cancel", api.post(f"/me/bookings/{booking_id}/cancel", headers=auth),
          test=lambda j: j["booking_status"] == "Cancelled")
    check("POST /me/bookings/{id}/cancel (again -> 409)", api.post(f"/me/bookings/{booking_id}/cancel", headers=auth), 409)

passed = sum(results)
print(f"\n{passed} of {len(results)} checks passed" + ("" if passed == len(results) else "  <-- look at the FAIL lines"))
sys.exit(0 if passed == len(results) else 1)
