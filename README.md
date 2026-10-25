# HotelAI — Nile Pearl Hotel

> **Final dataset.** This is the single version the whole team works from. It contains everything you need, and nothing extra.

HotelAI is an AI voice agent for hotel customer service. The agent ("Nour") answers guest questions from the hotel knowledge base and handles bookings, payments, and requests through the database. It speaks Egyptian Arabic with Egyptian guests and the guest's own language with everyone else.

The hotel and all its data are **fictional**, modeled on a real 5-star hotel in Cairo.

> [!IMPORTANT]
> **"Today" in the data is 19 September 2026.** Always read it from `app_settings.system_date` (or `hotel_today()` in SQL), never from the machine clock.

---

## Table of Contents

1. [Key Rules](#key-rules)
2. [The Hotel at a Glance](#the-hotel-at-a-glance)
3. [Repository Structure](#repository-structure)
4. [Getting Started](#getting-started)
5. [Backend API](#backend-api)
6. [How the System Works](#how-the-system-works)
7. [Database](#database)
8. [Demo Data](#demo-data)
9. [Evaluation & Tests](#evaluation--tests)
10. [Changelog](#changelog)

---

## Key Rules

1. **Work on this version only.** Edit the knowledge base and FAQ here, then run `build_rag.py` and `check_data.py`.
2. **"Today" = 19 September 2026**, taken from `app_settings.system_date` / `hotel_today()`, not the system clock.
3. **The agent only discusses bookings in the logged-in guest's account.** A booking made elsewhere is linked to the account once, using the booking number + last name, or the last 4 digits of the phone number.
4. Full business rules are in [`docs/BUSINESS_RULES.md`](docs/BUSINESS_RULES.md). Who answers which question is in [`docs/ROUTING.md`](docs/ROUTING.md).

---

## The Hotel at a Glance

| | |
|---|---|
| **Name** | Nile Pearl Hotel (5-star) |
| **Address** | 14 Corniche El Nil Street, Garden City, Cairo, Egypt |
| **Reception (24/7)** | +20 2 2794 5500 |
| **Reservations** | +20 2 2794 5501 |
| **Rooms** | 150 rooms on floors 2–16. Room number = floor × 100 + n (e.g., `1307`) |
| **Views** | Rooms 1–5 on each floor and every Suite face the Nile |
| **Check-in / Check-out** | 3:00 PM / 12:00 PM |
| **Currency** | EGP. Prices include 12% service, 14% VAT, and 1% city tax |

| Room type | Capacity | Size | Base rate / night | Rooms | Photos |
|---|---|---|---|---|---|
| Single | 1 | 28 m² | 6,000 EGP | 20 | Nile + City |
| Double | 2 | 34 m² | 8,000 EGP | 35 | Nile + City |
| Twin | 2 | 34 m² | 8,500 EGP | 30 | Nile + City |
| Deluxe | 3 | 45 m² | 12,000 EGP | 30 | Nile + City |
| Family | 4 | 60 m² | 14,000 EGP | 20 | Nile + City |
| Suite | 4 | 85 m² | 20,000 EGP | 15 | Nile only |

Children count toward capacity. An extra bed (2,500 EGP/night) does not raise capacity, so a party of 5 or more needs two rooms.

---

## Repository Structure

| Folder | Contents | Used by |
|---|---|---|
| `database/` | Ready-to-use PostgreSQL database: 23 tables, seed data, the queries the API needs (`queries.sql`), SQL tests, ERD, and data dictionary | Backend, System Analysis |
| `app/api/` | Backend API (FastAPI) on top of the database | Backend, Frontend |
| `app/rag/` | Retrieval code (BM25 + BGE-M3), prompt, router, and the agent's tools | RAG team |
| `app/prototype/` | End-to-end prototype: voice in → Whisper → RAG → LLM + tools → Egyptian voice reply. Includes a ready Colab notebook | RAG, Speech |
| `tests/` | API tests (pytest) | Backend |
| `knowledge_base/` | 44 files with all hotel information, policies, and prices. The agent answers from these | RAG team |
| `rag/` | The knowledge base split into 157 chunks, plus 3,996 Q&A pairs in 5 languages | RAG team |
| `evaluation/` | 200 realistic Egyptian-Arabic questions, 630 conversations, and the Egyptian-dialect review file | Everyone |
| `docs/` | Hotel business rules and question routing | Everyone |
| `scripts/` | `build_rag.py` and `check_data.py` | RAG team |
| `static/` | Room photos (`rooms/`) and hotel photos (`hotel/`), served by the API at `/static/...` | Backend, Frontend |

**Root files**

| File | Purpose |
|---|---|
| `requirements.txt` | RAG dependencies (the BM25 mode needs only the Python standard library) |
| `requirements-api.txt` | Backend API and test dependencies |
| `.env` | Database connection for the API. Not committed to git |
| `pytest.ini` | Test settings |
| `CHANGES_v7.md` | Old v7 change notes (Arabic) |

---

## Getting Started

### 1. Database

The easiest way is Docker:

```bash
cd database
docker compose up -d   # PostgreSQL 16; all data loads automatically on first run
```

- Connection: `postgresql://hotelai:hotelai@localhost:5432/hotelai`
- Start again from scratch: `docker compose down -v && docker compose up -d`
- Other options (a local PostgreSQL install, or pgAdmin) are explained in [`database/README.md`](database/README.md).

### 2. Backend API

Run these from the **project root** (the API reads `.env` from the current folder):

```bash
pip install -r requirements-api.txt

# Create .env in the project root with:
# DATABASE_URL=postgresql://hotelai:hotelai@localhost:5432/hotelai

uvicorn app.api.main:app --reload
```

Open <http://localhost:8000/docs> to try every endpoint. Details are in [Backend API](#backend-api).

### 3. RAG

```bash
# Offline evaluation (BM25 only, no internet needed)
python -m app.rag.evaluate --mode bm25

# Hybrid evaluation with BGE-M3
pip install -r requirements.txt
python -m app.rag.evaluate --mode hybrid

# Ask a question and print the full prompt
python -m app.rag.demo "الفطار بكام؟" --show-prompt   # "How much is breakfast?"
```

### 4. Prototype (voice)

Open `app/prototype/HotelAI_Prototype.ipynb` on Google Colab, select a **T4 GPU**, upload the project zip, and run the cells in order. It is free and needs no API key. See [`app/prototype/README.md`](app/prototype/README.md).

### 5. After editing the knowledge base or FAQ

After **any** change in `knowledge_base/` or `rag/hotel_faq_gold.csv`:

```bash
python scripts/build_rag.py    # rebuilds the chunks and the FAQ index
python scripts/check_data.py   # must pass 10/10
```

---

## Backend API

FastAPI + async SQLAlchemy (asyncpg) on the PostgreSQL database. Code is in `app/api/`:

| Folder / file | Contents |
|---|---|
| `main.py` | App setup: CORS, rate limiting, request logging, error handler, `/static` |
| `config.py` | Settings read from `.env` |
| `db.py` | Database connection pool |
| `routers/` | Endpoints |
| `schemas/` | Request and response models (Pydantic) |
| `services/` | Pricing and discount-code logic |

### Endpoints

| Method | Path | What it returns |
|---|---|---|
| `GET` | `/` | A message that the API is running |
| `GET` | `/health` | Database status, the hotel's "today", and the room count |
| `GET` | `/availability` | Free rooms and prices for a room type and dates (see below) |
| `GET` | `/room-types` | All room types: description, capacity, size, base price, photos |
| `GET` | `/hotel-photos` | Hotel area photos. Optional `photo_key`: `hotel`, `lobby`, `pool`, `spa`, `gym`, `restaurant` |
| `GET` | `/menu` | Room-service menu and the delivery charge. Optional `night_only` and `category` |
| `GET` | `/discount-codes/{code}` | Whether a discount code can be used today |
| `GET` | `/static/...` | Room and hotel images |

**`GET /availability` parameters:** `room_type` (name or ID), `check_in`, `check_out`, `guests` (1–10, default 1), and an optional `discount_code`.

It returns the free room numbers, how many face the Nile, the room photos, and two prices:

- **Flexible:** total, the one discount applied, amount due, deposit to pay now, and the amount to pay at the hotel.
- **Non-refundable:** total and amount to pay now.

If no room is free, it returns **alternatives**: other room types that fit the guests, with their free-room counts.

### Behavior

- **Errors** return a `reason` code the frontend can act on: `UNKNOWN_ROOM_TYPE`, `CHECK_IN_IN_THE_PAST`, `CAPACITY_EXCEEDED`, `CODE_NOT_FOUND`, `PHOTO_NOT_FOUND`, `TOO_MANY_REQUESTS`.
- **Rate limit:** 60 requests per minute per IP address. Change it with `RATE_LIMIT` in `.env`.
- **Logs:** every request is logged to the console and to `logs/api.log` (rotating: 5 MB × 3 files).
- **CORS:** allows `http://localhost:5173` and `http://localhost:3000` by default.

> [!NOTE]
> **Login is not in the API yet.** Until it is, personal discount codes answer `PERSONAL_CODE_LOGIN_REQUIRED`.

---

## How the System Works

A summary of the main rules. The full list is in [`docs/BUSINESS_RULES.md`](docs/BUSINESS_RULES.md).

### Accounts & Login

- The agent identifies the guest through their **account (login)**. It no longer asks for a booking number and last name.
- `user_accounts` holds everyone who logs in: guests, staff, and admins.
- A logged-in guest sees their bookings directly, with no further questions: their own bookings plus any linked to the account (`my_bookings` tool, `v_account_bookings` view).
- Bookings made by phone, through a travel agency, or on a booking site are linked to the account **once**, using the booking number + last name (English or Arabic spelling) or the last 4 digits of the phone number (`link_booking` tool, stored in `booking_links`).
- **Visitors** (not logged in) get general answers only. Booking, managing a booking, and requests need a login.
- `verification_codes` handles email confirmation and password reset (query 12 in `queries.sql`). A code works once, for 10 minutes, with 5 attempts.
- The agent never asks for card numbers or security codes.

### Rate Plans & Payment

| | Flexible | Non-refundable |
|---|---|---|
| **Price** | Standard rate | 15% lower |
| **Payment** | First night online as a deposit (payment link); the rest at the hotel | Full amount at booking |
| **Cancel 48 h+ before 3 PM on arrival day** | Free: the deposit is refunded automatically through the payment gateway | Nothing refunded |
| **Cancel later, or no-show** | The deposit is kept as the first-night charge; nothing more is charged | Nothing refunded |
| **Change dates or room** | Free until 48 h before arrival | Not allowed |
| **Discounts** | One discount (see below) | None |

Refunds are processed within 3 business days. Card refunds appear 7–14 business days later.

### Booking Statuses & Payment Deadline

| Status | Meaning |
|---|---|
| `Pending` | Booked, waiting for the payment link to be paid. The room is held |
| `Confirmed` | Paid; upcoming or in progress |
| `Completed` | Stayed and left |
| `Cancelled` | Cancelled |
| `No-show` | Did not arrive |

- The payment link is valid for **24 hours**, or **2 hours** if arrival is less than 24 hours away.
- Paid in time → the booking becomes `Confirmed`.
- Not paid → the booking is cancelled automatically, the payment becomes `Expired`, and the room is released.
- A declined card does not extend the deadline; the agent can resend the link.
- The deadline is stored in `payments.payment_due_at`. Queries 4, 4b, and 4c in `queries.sql`.

### Modifying a Booking

- The agent modifies bookings **by itself** after checking availability (`quote_modification` tool, query 9).
- New dates and extra nights → the same agreed nightly rate.
- Room type change → the base rate of the new room type.
- Booking.com bookings must be modified through Booking.com.

### Discounts

- The agent applies **one discount only**, whichever is larger:
  - **Extended stay:** 12% off for 7 nights or more.
  - **A valid discount code.**
- Discounts apply to the **Flexible rate only**. The database rejects any discount on a Non-refundable booking.
- `check_availability` calculates the discount and returns the price after discount. The router passes `account_id` so personal codes work.
- The applied discount is stored on the booking (`discount_source`, `discount_code_id`, `discount_amount`), and `amount_due` = total after discount.
- Member, corporate, group, and low-season rates are arranged by the reservations team.
- **Any other discount** becomes a `Discount Request` for the admin to decide (`customer_requests.decision`). If approved, a **one-time personal code** is created for that guest only (`discount_codes.customer_id`) and sent by email (query 11).

### Customer Requests (Tickets)

Every ticket is a row in `customer_requests` (query 10). The agent opens them with the `create_request` tool.

| Request type | Notes |
|---|---|
| In-stay and service requests | Room Service, Housekeeping, Airport Transfer, Early Check-in, Late Checkout, Extra Bed, and inquiries (Booking, Payment, General, Modification, Cancellation) |
| `Maintenance` | AC, lights, taps, etc. |
| `Complaint` | Category: Room, Service, Facility, Billing, or Booking Issue |
| `Special Request` | Needs a booking and a category; staff approve or reject it (`decision`) |
| `Discount Request` | The admin decides (`decision`) |
| `Staff Callback` | Always `Urgent`. Can be opened by a visitor |
| `Emergency` | Always `Critical`. Can be opened by a visitor |

- **Login:** tickets need a logged-in guest, except an `Emergency` or `Staff Callback` from a visitor, which is linked to the call (`call_id`).
- **Priority:** `Critical` = Emergency only. `Urgent` = Staff Callback or a serious complaint. Otherwise `Normal`.
- **Status:** `Open` (no one has it) → `In Progress` (`handled_by`) → `Resolved` (done) or `Closed` (not done: rejected, cancelled, or the stay ended). `resolved_at` is set only at the end.
- **Staff queue:** only tickets that can still be acted on: from the last 14 days, or a service for a current or upcoming stay. Stay services (housekeeping, room service, special requests, …) end with the stay.

### Staff Handoff & Emergencies

- The agent transfers to a staff member **only** when the guest has a problem and asks for it. The transfer is a **live chat** with a free staff member.
- If no staff member is free, an urgent `Staff Callback` ticket is opened, and staff contact the guest in the chat or by email.
- In an emergency, the agent gives the hotel reception number (+20 2 2794 5500) and the emergency numbers below, then opens an `Emergency` ticket with `Critical` priority, shown first on the staff dashboard.

| Service | Number |
|---|---|
| Ambulance | 123 |
| Police | 122 |
| Fire | 180 |

### Front Desk Operations

- Staff record check-in, check-out, and the remaining balance from the dashboard (query 8; columns `checked_in_at` and `checked_out_at`).
- `rooms.status = 'Occupied'` means a guest is currently checked in.

### Photos

- **Room photos:** `room_types.image_nile` and `room_types.image_city`. The Suite has a Nile photo only, since every Suite faces the Nile.
- **Hotel photos:** the `hotel_photos` table links photos to hotel areas (hotel, lobby, pool, spa, gym, restaurant). The agent shows them with the `hotel_photos` tool.

### Settings (`app_settings`)

| Key | Value | Purpose |
|---|---|---|
| `system_date` | `2026-09-19` | The hotel's "today" |
| `timezone` | `Africa/Cairo` | Hotel time zone |
| `hotel_name` | `Nile Pearl Hotel` | Hotel name |
| `check_in_time` | `15:00` | Standard check-in time |
| `check_out_time` | `12:00` | Standard check-out time |
| `free_cancellation_hours` | `48` | Flexible rate: free cancellation until this many hours before 3 PM on arrival day |
| `deposit_nights` | `1` | Nights paid online as the deposit |
| `deposit_hold_hours` | `24` | How long a new booking stays `Pending` waiting for payment |
| `deposit_hold_hours_last_minute` | `2` | The hold when arrival is less than 24 hours away |
| `currency` | `EGP` | All prices in Egyptian Pounds, taxes included |
| `reception_phone` | `+20 2 2794 5500` | Reception, 24/7 |
| `reservations_phone` | `+20 2 2794 5501` | Reservations line |
| `otp_valid_minutes` | `10` | How long a verification code works |
| `otp_max_attempts` | `5` | Wrong attempts allowed for one code |

---

## Database

PostgreSQL 16 with **23 tables**. Column details are in [`database/DATA_DICTIONARY.md`](database/DATA_DICTIONARY.md) and the diagram in [`database/ERD.png`](database/ERD.png).

| Area | Tables |
|---|---|
| Hotel & rooms | `room_types`, `rooms`, `services`, `fees`, `menu_items`, `hotel_photos` |
| Guests & loyalty | `customers`, `loyalty_tiers`, `loyalty_rules`, `loyalty_members` |
| Pricing | `pricing_tiers`, `discount_codes` |
| Bookings & payments | `bookings`, `payments`, `booking_links` |
| Guest service | `customer_requests`, `customer_feedback` |
| Accounts | `user_accounts`, `verification_codes` |
| Calls | `calls`, `call_messages`, `call_actions` |
| Settings | `app_settings` |

**Views & functions:** `v_booking_details`, `v_account_bookings`, `v_call_overview`, `hotel_today()`, `free_rooms()`.

**Data size:** 10,000 customers, 16,534 bookings (one payment each), 13,756 tickets, and 5,599 accounts (5,594 guests, 4 staff, 1 admin).

### What the database guarantees

- Two `Pending`, `Confirmed`, or `Completed` bookings never share a room on the same night (exclusion constraint `no_double_booking`).
- A booking's room is of the booked room type, and the guests fit its capacity.
- Nights are `[check_in, check_out)`, so back-to-back stays are allowed.
- `nights`, `total_amount`, and `amount_due` are computed by the database.
- Every confirmed or completed booking has a real room, with the room number the guest hears (e.g., `1307`).
- Every customer's registration date is before their first stay, and every booker is 18 or older.
- Complaints, special requests, and reviews have text that matches their type.
- Check-in and check-out are recorded for every completed stay and for every in-house guest who arrived before today. Today's arrivals have not checked in yet.
- `calls.account_id` shows who is calling (`NULL` = visitor).

---

## Demo Data

17 connected demo calls (`calls`, `call_messages`, `call_actions`) between 14 and 19 September 2026:

- New booking with the extended-stay discount (`B020001`)
- New booking with a personal code (`B020002`)
- 4 discount requests: 2 approved with personal codes (`DC030`, `DC031`), 1 rejected, 1 waiting for the admin
- Medical emergency (visitor, not logged in) and fire emergency
- Transfer to staff via live chat
- Staff Callback (no staff free)
- Maintenance, special request, and complaint
- Payment status question
- Visitor asked to log in
- Linking a travel-agency booking
- A dropped call

**Demo password for all accounts:** `NilePearl@2026`

---

## Evaluation & Tests

### Evaluation set (`evaluation/`)

- **200 realistic Egyptian questions** (`realistic_test_egyptian.csv`), each with an `account_id` column. 51 are asked by a logged-in guest whose stay matches the question (booking questions, complaints, and requests). Emergency and safety questions are asked by visitors.
- **630 conversations** (`conversations.csv`), each with an `account_id` column:
  - Medical and fire emergencies include the emergency numbers, reception, and alerting the team. Theft includes the police number.
  - Staff transfer is a live chat.
  - Includes a visitor-login flow (`INT012_F6_visitor_login`) and a discount-request flow (`INT027_F2_discount_request`), 5 conversations each.
- **Egyptian-dialect review** (`egyptian_review.xlsx`).

### Tests

| Test | What it checks | How to run |
|---|---|---|
| `database/tests/run_checks.sql` | 39 data integrity checks | `psql -d hotelai -f tests/run_checks.sql` (from `database/`) |
| `database/tests/constraint_checks.sql` | 16 checks that the database refuses invalid data | `psql -d hotelai -f tests/constraint_checks.sql` (from `database/`) |
| `scripts/check_data.py` | RAG files, FAQ, and knowledge base vs database | `python scripts/check_data.py` |
| `tests/` | 23 API tests: availability, pricing, discounts, hotel info | `pytest` (the database must be running) |
| `app/prototype/test_agent.py` | Agent behavior on the realistic questions and 5 languages, including login/logout | See the prototype README |

Every line must say `PASS`, and `check_data.py` must pass **10/10**.

---

## Changelog

### Backend API (October 2026, latest)

- FastAPI app with settings from `.env`, an async database connection pool, and `/health`.
- CORS, routers, and static images.
- Request logging and a global error handler.
- `GET /availability`: validation, free rooms, Nile-view count, photos, alternatives, and Flexible / Non-refundable pricing with the one discount.
- `GET /room-types`, `/hotel-photos`, `/menu`, and `/discount-codes/{code}`.
- Rate limiting (60 requests/minute).
- pytest suite (23 tests).

### v8 — Final data

Marked as final: any change after this is for new features only.

- Merged `complaint_tickets` and `special_requests` into **`customer_requests`** (database back to 23 tables), with new columns `handled_by`, `resolved_at`, `call_id`, and `decision`.
- Closed old tickets that had been open for months.
- Tickets require login, except `Emergency` and `Staff Callback`.
- `calls.account_id` replaces `identity_verified`.
- Check-in / check-out recorded for past and in-house stays; `rooms.status = Occupied` now means a guest is checked in.
- Discount rules: Flexible rate only, extended stay 12% or code (the larger). `check_availability` returns the discounted price; the router passes `account_id`.
- Added 17 connected demo calls.
- Updated emergency, theft, and handoff conversations; added visitor-login and discount-request flows.
- Added account topics to `reservation_security.txt` plus 15 new FAQ entries (3 questions × 5 languages, intent `INT034`).
- 22 complaint and request questions are now asked by logged-in guests.
- Tests: `run_checks.sql` → 39 checks, `constraint_checks.sql` → 16 checks.

### v6–v7 — Accounts, deposits, and new features (October 2026)

- **Login replaces booking number + last name.** Updated `router.py`, `agent.py` (`login` / `logout`), `test_agent.py`, the 630 conversations and 200 questions (new `account_id` column). Created accounts for 5 guests who needed one.
- **Deposit payment** for the Flexible rate. Updated the knowledge base, the FAQ in 5 languages, the `payments` table, `run_checks.sql`, the tools, and the evaluation set.
- **Payment deadline** with automatic cancellation (`payments.payment_due_at`).
- New tables: `user_accounts`, `booking_links`, `verification_codes`, `hotel_photos`.
- Agent-driven **booking modification**.
- **Discounts** stored on bookings; admin-approved discount requests with personal one-time codes.
- **Automatic deposit refunds** through the payment gateway.
- Staff **check-in / check-out** from the dashboard.
- **Live-chat handoff**, `Staff Callback`, and `Emergency` tickets; new `priority` column and `create_request` tool.
- Full hotel **address** in answers.
- **Photos:** `static/` folder, `image_nile` / `image_city` columns, `hotel_photos` table and tool.
- New request type: **`Maintenance`**.
- New settings: `deposit_nights`, `otp_valid_minutes`, `otp_max_attempts`.

Detailed v7 notes are in [`CHANGES_v7.md`](CHANGES_v7.md) (Arabic).

### Changes from HotelAI_v4

- **Removed 3,468 bookings with no room**, along with everything linked to them.
- Rooms now use their **real room number** instead of an internal code.
- Fixed customer data (registration dates, booker ages).
- Complaint, special request, and review text now matches its type (e.g., a "Room Issue" complaint no longer talks about an "Unexpected charge").
- Removed raw data, reports, old scripts, fine-tuning files, and the archive. The full history of every change is in **HotelAI_v4**.
