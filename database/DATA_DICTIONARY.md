# Data dictionary - Nile Pearl Hotel database

Every table and column of `schema.sql`. The same descriptions are stored in the database as column comments
(pgAdmin shows them; `\d+ table` in psql). If you change `schema.sql`, update this file too.

| Table | Group | Rows (demo data) | What it holds |
|---|---|---|---|
| [`app_settings`](#app_settings) | Hotel settings | 14 | Hotel-wide settings. system_date is the frozen "today" of the dataset; the API must use it instead of the machine clock while the demo data is in use. |
| [`room_types`](#room_types) | Rooms | 6 | The six room categories, their capacity and standard nightly rate (EGP, taxes included, room only). |
| [`rooms`](#rooms) | Rooms | 150 | 150 rooms on floors 2-16. room_number = floor x 100 + n; rooms 1-5 of a floor and every Suite face the Nile. |
| [`customers`](#customers) | Guests | 10,000 | Guests. Arab guests also carry the Arabic spelling of their name, so a caller who gives an Arabic name is found. |
| [`loyalty_tiers`](#loyalty_tiers) | Loyalty | 4 | Nile Pearl Rewards tiers: nights needed per calendar year, points bonus and free late check-out. |
| [`loyalty_rules`](#loyalty_rules) | Loyalty | 7 | Programme rules as numbers: earn rate, redemption, expiry, referral bonus, member discount. |
| [`loyalty_members`](#loyalty_members) | Loyalty | 100 | Programme members: one membership per guest. |
| [`pricing_tiers`](#pricing_tiers) | Pricing | 10 | Special rates as multipliers of the standard Flexible rate. Only one discount applies to a booking. |
| [`discount_codes`](#discount_codes) | Pricing | 31 | Promotional codes. status is derived on system_date: Expired, Scheduled, Exhausted or Active. |
| [`services`](#services) | Services | 16 | Priced hotel services (breakfast, transfers, spa, laundry, extra bed, late check-out...). |
| [`fees`](#fees) | Services | 10 | Fees and percentages from the hotel policies: deposit, smoking fee, early/late check-out, cancellation. |
| [`menu_items`](#menu_items) | Services | 23 | In-room dining and restaurant menu. Room service adds the delivery charge of service S002 per order. |
| [`bookings`](#bookings) | Reservations | 16,534 | Reservations. Every Pending, Confirmed or Completed booking occupies its room; the database refuses two of them on the same room and nights. |
| [`payments`](#payments) | Reservations | 16,534 | One payment record per booking: what was collected and refunded. |
| [`customer_requests`](#customer_requests) | Guest service | 13,756 | Every ticket for the hotel team: service requests, maintenance, complaints, special requests, discount requests, staff callbacks and emergencies. |
| [`customer_feedback`](#customer_feedback) | Guest service | 4,001 | Reviews of finished stays: one per booking. |
| [`user_accounts`](#user_accounts) | Accounts | 5,599 | One login for everyone: guests (linked to a customer), hotel staff and admins. |
| [`verification_codes`](#verification_codes) | Accounts | 0 | One-time codes sent by email to confirm the email at sign-up or to reset a password. Only a hash of the code is stored. Filled by the API. |
| [`booking_links`](#booking_links) | Accounts | 21 | Bookings made elsewhere that a guest added to the account after the reference check. |
| [`hotel_photos`](#hotel_photos) | Hotel | 6 | Photos of the hotel areas (pool, spa, gym, restaurant, lobby, building) that the agent can show during a call. Room photos are in room_types. |
| [`calls`](#calls) | Dashboard | 17 | One row per conversation with the voice agent (voice or text). Filled by the API; shown on the dashboard. The demo data has 17 sample calls. |
| [`call_messages`](#call_messages) | Dashboard | 90 | Every turn of every call: what the guest said (after speech-to-text) and what the agent answered. |
| [`call_actions`](#call_actions) | Dashboard | 22 | What the agent did during a call: each tool it ran (availability check, booking lookup, cancellation...) and the result. |

## app_settings

Hotel-wide settings. system_date is the frozen "today" of the dataset; the API must use it instead of the machine clock while the demo data is in use.

Rows in the demo data: **14**

| Column | Type | Rules | Description |
|---|---|---|---|
| `key` | VARCHAR(40) | PK, required | Setting name |
| `value` | TEXT | required | Setting value (text; cast in the application) |
| `description` | TEXT | optional | What the setting means |

## room_types

The six room categories, their capacity and standard nightly rate (EGP, taxes included, room only).

Rows in the demo data: **6**

| Column | Type | Rules | Description |
|---|---|---|---|
| `room_type_id` | VARCHAR(5) | PK, required | RT001-RT006 |
| `room_type_name` | VARCHAR(20) | required, unique | Single, Double, Twin, Deluxe, Family, Suite |
| `description` | TEXT | required | Short description |
| `capacity` | SMALLINT | required, capacity BETWEEN 1 AND 4 | Maximum guests, adults and children together |
| `base_price` | NUMERIC(10,2) | required, base_price > 0 | Standard Flexible rate per night, EGP |
| `size_sqm` | SMALLINT | required, size_sqm > 0 | Room size in square metres |
| `image_nile` | VARCHAR(80) | required | Photo of the room type with a Nile view (path under static/) |
| `image_city` | VARCHAR(80) | optional | Photo with a city view; NULL for the Suite (every Suite faces the Nile) |

## rooms

150 rooms on floors 2-16. room_number = floor x 100 + n; rooms 1-5 of a floor and every Suite face the Nile.

Rows in the demo data: **150**

| Column | Type | Rules | Description |
|---|---|---|---|
| `room_number` | SMALLINT | PK, required | Room number as told to the guest, e.g. 1307 |
| `floor` | SMALLINT | required, floor BETWEEN 2 AND 16 | Floor |
| `room_type_id` | VARCHAR(5) | FK → room_types, required | Room type |
| `view` | VARCHAR(4) | required, one of: Nile, City | Nile or City |
| `status` | VARCHAR(11) | required, one of: Available, Occupied, Maintenance | Snapshot on system_date: Occupied = a guest is checked in now. Availability for any dates is computed from bookings, not from this column; a room in Maintenance is never offered. |

Table rules:
- `UNIQUE (room_number, room_type_id)`

## customers

Guests. Arab guests also carry the Arabic spelling of their name, so a caller who gives an Arabic name is found.

Rows in the demo data: **10,000**

| Column | Type | Rules | Description |
|---|---|---|---|
| `customer_id` | VARCHAR(7) | PK, required, auto: next reference | C + 6 digits |
| `first_name` | VARCHAR(40) | required | First name (Latin) |
| `last_name` | VARCHAR(40) | required | Last name (Latin) |
| `first_name_ar` | VARCHAR(40) | optional | First name in Arabic, Arab guests only |
| `last_name_ar` | VARCHAR(40) | optional | Last name in Arabic, Arab guests only |
| `email` | VARCHAR(120) | required, unique | Email |
| `phone` | VARCHAR(20) | required, unique | Phone in international format; its last 4 digits are used for the identity check |
| `nationality` | VARCHAR(30) | optional | Nationality (optional at sign-up) |
| `date_of_birth` | DATE | optional | Date of birth (asked before the first booking: the guest must be 18+) |
| `created_at` | TIMESTAMPTZ | required, default now() | Account creation time (Cairo time) |

## loyalty_tiers

Nile Pearl Rewards tiers: nights needed per calendar year, points bonus and free late check-out.

Rows in the demo data: **4**

| Column | Type | Rules | Description |
|---|---|---|---|
| `tier` | VARCHAR(10) | PK, required | Standard, Silver, Gold, Platinum |
| `min_nights_per_year` | SMALLINT | required, min_nights_per_year >= 0 | Nights in a calendar year to reach the tier |
| `points_bonus_pct` | SMALLINT | required, points_bonus_pct >= 0 | Extra points on top of the base earn rate, % |
| `late_checkout_until` | TIME | optional | Free late check-out until this time (NULL = none) |
| `benefits` | TEXT | required | Benefits as told to the guest |

## loyalty_rules

Programme rules as numbers: earn rate, redemption, expiry, referral bonus, member discount.

Rows in the demo data: **7**

| Column | Type | Rules | Description |
|---|---|---|---|
| `rule` | VARCHAR(30) | PK, required | Rule name |
| `value` | NUMERIC(10,2) | required | Rule value |
| `unit` | VARCHAR(20) | required | Unit of the value |
| `note` | TEXT | required | Meaning |

## loyalty_members

Programme members: one membership per guest.

Rows in the demo data: **100**

| Column | Type | Rules | Description |
|---|---|---|---|
| `member_id` | VARCHAR(7) | PK, required, auto: next reference | LM + 5 digits |
| `customer_id` | VARCHAR(7) | FK → customers, required, unique | The member |
| `tier` | VARCHAR(10) | FK → loyalty_tiers, required | Current tier |
| `join_date` | DATE | required | Joining date |
| `points_balance` | INTEGER | required, points_balance >= 0 | Points available |
| `total_stays` | INTEGER | required, total_stays >= 0 | Lifetime stays |
| `status` | VARCHAR(10) | required, one of: Active, Inactive | Membership status |

## pricing_tiers

Special rates as multipliers of the standard Flexible rate. Only one discount applies to a booking.

Rows in the demo data: **10**

| Column | Type | Rules | Description |
|---|---|---|---|
| `pricing_tier_id` | VARCHAR(5) | PK, required | PT001-PT010 |
| `tier_name` | VARCHAR(30) | required, unique | Rate name |
| `description` | TEXT | required | When it applies |
| `rate_multiplier` | NUMERIC(4,2) | required, rate_multiplier > 0 | Multiplier of the Flexible rate, e.g. 0.85 = 15% off |
| `status` | VARCHAR(10) | required, one of: Active, Inactive | Status |

## discount_codes

Promotional codes. status is derived on system_date: Expired, Scheduled, Exhausted or Active.

Rows in the demo data: **31**

| Column | Type | Rules | Description |
|---|---|---|---|
| `code_id` | VARCHAR(5) | PK, required | DC001-DC029 public codes; DC030-DC031 personal codes issued for approved Discount Requests |
| `discount_code` | VARCHAR(20) | required, unique | Code the guest gives, e.g. PEARL100 |
| `discount_type` | VARCHAR(12) | required, one of: PERCENTAGE, FIXED_AMOUNT | Percentage or fixed EGP amount |
| `discount_value` | NUMERIC(10,2) | required, discount_value > 0 | Percent (1-100) or EGP |
| `usage_count` | INTEGER | required, usage_count >= 0 | Times used |
| `max_usage` | INTEGER | optional, max_usage > 0 | Usage limit (NULL = unlimited) |
| `start_date` | DATE | required | First valid day |
| `end_date` | DATE | required | Last valid day |
| `status` | VARCHAR(10) | required, one of: Active, Scheduled, Exhausted, Expired | Status on system_date |
| `customer_id` | VARCHAR(7) | FK → customers, optional | Personal code: only this guest can use it, once (max_usage = 1). Issued when the administrator approves a Discount Request. NULL = a public code |

Table rules:
- `CHECK (end_date >= start_date)`
- `CHECK (customer_id IS NULL OR max_usage = 1)`
- `CHECK (max_usage IS NULL OR usage_count <= max_usage)`
- `CHECK (discount_type <> 'PERCENTAGE' OR discount_value <= 100)`

## services

Priced hotel services (breakfast, transfers, spa, laundry, extra bed, late check-out...).

Rows in the demo data: **16**

| Column | Type | Rules | Description |
|---|---|---|---|
| `service_id` | VARCHAR(4) | PK, required | S001-S016 |
| `service_name` | VARCHAR(40) | required, unique | Service |
| `category` | VARCHAR(30) | required | Category |
| `description` | TEXT | required | Description |
| `price` | NUMERIC(10,2) | required, price >= 0 | Price in EGP (0 = free for guests) |
| `unit` | VARCHAR(20) | required | per_person, per_trip, per_kg, per_night... |
| `is_available` | BOOLEAN | required, default true | Offered now |

## fees

Fees and percentages from the hotel policies: deposit, smoking fee, early/late check-out, cancellation.

Rows in the demo data: **10**

| Column | Type | Rules | Description |
|---|---|---|---|
| `fee_id` | VARCHAR(4) | PK, required | F001-F010 |
| `fee_name` | VARCHAR(60) | required, unique | Fee |
| `amount` | NUMERIC(10,2) | required | Amount in the given unit |
| `unit` | VARCHAR(30) | required | EGP_per_night, percent_of_nightly_rate, nights... |
| `rule` | TEXT | required | When it applies |

## menu_items

In-room dining and restaurant menu. Room service adds the delivery charge of service S002 per order.

Rows in the demo data: **23**

| Column | Type | Rules | Description |
|---|---|---|---|
| `item_id` | VARCHAR(3) | PK, required | M01-M23 |
| `name_en` | VARCHAR(60) | required, unique | Dish (English) |
| `name_ar` | VARCHAR(60) | required, unique | Dish (Arabic) |
| `category` | VARCHAR(20) | required | Starters, Sandwiches, Main courses, Children, Desserts, Drinks |
| `price` | NUMERIC(10,2) | required, price > 0 | Price in EGP, taxes included |
| `dietary` | VARCHAR(20) | optional | Codes: V vegetarian, G gluten, D dairy, E egg, N nuts, F fish |
| `night_menu` | BOOLEAN | required | Served 11 PM - 6 AM |

## bookings

Reservations. Every Pending, Confirmed or Completed booking occupies its room; the database refuses two of them on the same room and nights.

Rows in the demo data: **16,534**

| Column | Type | Rules | Description |
|---|---|---|---|
| `booking_id` | VARCHAR(7) | PK, required, auto: next reference | Booking reference told to the guest: B + 6 digits |
| `customer_id` | VARCHAR(7) | FK → customers, required | Guest who holds the booking |
| `room_number` | SMALLINT | FK → rooms (with the other column), required | Assigned room |
| `room_type_id` | VARCHAR(5) | FK → rooms (with the other column), required | Booked room type (must be the type of the room) |
| `check_in` | DATE | required | Arrival date (check-in from 3:00 PM) |
| `check_out` | DATE | required | Departure date (check-out by 12:00 PM) |
| `nights` | INTEGER | computed | Computed: check_out - check_in |
| `adults` | SMALLINT | required, adults >= 1 | Adults |
| `children` | SMALLINT | required, children >= 0, default 0 | Children (count toward capacity) |
| `booking_status` | VARCHAR(10) | required, one of: Pending, Confirmed, Completed, Cancelled, No-show | Pending (waiting for the payment link, room held), Confirmed, Completed, Cancelled, No-show |
| `booking_channel` | VARCHAR(20) | required, one of: Website, Booking Platform, Mobile App, Phone, Travel Agent, Voice Agent | Where it was booked; bookings made by the voice agent use "Voice Agent" |
| `rate_plan` | VARCHAR(14) | required, one of: Flexible, Non-refundable | Flexible: first night paid online as a deposit, the rest at the hotel; free cancellation until 48 h before arrival. Non-refundable: 15% cheaper, prepaid, no refund |
| `price_per_night` | NUMERIC(10,2) | required, price_per_night > 0 | Agreed nightly rate, EGP |
| `total_amount` | NUMERIC(12,2) | computed | Computed: price_per_night x nights (before any discount) |
| `discount_source` | VARCHAR(9) | optional, one of: Long Stay, Code | The one discount applied: Long Stay (7+ nights) or Code; NULL when none. When both apply, the bigger one is used |
| `discount_code_id` | VARCHAR(5) | FK → discount_codes, optional | The code used when discount_source = Code |
| `discount_amount` | NUMERIC(12,2) | required, discount_amount >= 0, default 0 | Discount in EGP (0 when none) |
| `amount_due` | NUMERIC(12,2) | computed | Computed: total_amount - discount_amount, what the guest pays for the stay |
| `created_at` | TIMESTAMPTZ | optional | When the booking was made (set by the API; in the demo data only for the two bookings made by the voice agent, B020001-B020002) |
| `cancelled_at` | TIMESTAMPTZ | optional | When it was cancelled (set by the API) |
| `checked_in_at` | TIMESTAMPTZ | optional | Arrival recorded by staff on the dashboard. Demo data: every Completed stay and every in-house stay that arrived before system_date (today's arrivals are still to check in) |
| `checked_out_at` | TIMESTAMPTZ | optional | Departure recorded by staff, with the balance paid at the hotel; only for Completed stays |

Table rules:
- `CHECK (check_out > check_in)`
- `CHECK ((discount_source IS NULL) = (discount_amount = 0))`
- `CHECK ((discount_source = 'Code') = (discount_code_id IS NOT NULL))`
- `CHECK (discount_amount < price_per_night * (check_out - check_in))`
- `CHECK (rate_plan = 'Flexible' OR discount_source IS NULL)` (Non-refundable is already the special price)
- `CHECK (discount_source IS DISTINCT FROM 'Long Stay' OR check_out - check_in >= 7)`
- `CHECK (checked_in_at IS NULL OR booking_status IN ('Confirmed', 'Completed'))`
- `CHECK (checked_out_at IS NULL OR (booking_status = 'Completed' AND checked_in_at IS NOT NULL AND checked_out_at >= checked_in_at))`
- `FOREIGN KEY (room_number, room_type_id) REFERENCES rooms (room_number, room_type_id)`
- `CONSTRAINT no_double_booking EXCLUDE USING gist (room_number WITH =, daterange(check_in, check_out, '[)') WITH &&) WHERE (booking_status IN ('Pending', 'Confirmed', 'Completed'))`

## payments

One payment record per booking: what was collected and refunded.

Rows in the demo data: **16,534**

| Column | Type | Rules | Description |
|---|---|---|---|
| `payment_id` | VARCHAR(7) | PK, required, auto: next reference | P + 6 digits |
| `booking_id` | VARCHAR(7) | FK → bookings, required, unique | The booking |
| `payment_method` | VARCHAR(20) | required, one of: Credit Card, Debit Card, Cash, Digital Wallet, Bank Transfer | Method |
| `amount_paid` | NUMERIC(12,2) | required, amount_paid >= 0, default 0 | Collected, EGP: Flexible = the first-night deposit until the stay is completed, then the total; Non-refundable = the total (0 when Pending or Failed) |
| `payment_status` | VARCHAR(20) | required, one of: Pending, Paid, Failed, Expired, Refunded, Partially Refunded | Expired = the link was not paid in time and the booking was cancelled |
| `refund_amount` | NUMERIC(12,2) | required, refund_amount >= 0, default 0 | Refunded, EGP |
| `transaction_reference` | UUID | required, unique, default gen_random_uuid() | Gateway reference |
| `payment_due_at` | TIMESTAMPTZ | optional | Deadline to pay the link of a Pending booking (24 h, or 2 h when arrival is less than 24 h away) |
| `created_at` | TIMESTAMPTZ | optional | When it was recorded (set by the API) |

Table rules:
- `CHECK (refund_amount <= amount_paid)`

## customer_requests

Every ticket for the hotel team: service requests, maintenance, complaints, special requests, discount requests, staff callbacks and emergencies (complaints and special requests used to be two other tables). In-stay requests are dated inside the stay; requests without a stay have no booking.

Rows in the demo data: **13,756**

| Column | Type | Rules | Description |
|---|---|---|---|
| `request_id` | VARCHAR(9) | PK, required, auto: next reference | REQ + 6 digits |
| `customer_id` | VARCHAR(7) | FK → customers, optional | Guest (from the login). NULL only for an Emergency or Staff Callback raised by a visitor who is not logged in; `call_id` then says where it came from |
| `booking_id` | VARCHAR(7) | FK → bookings, optional | Related booking (required for a Special Request) |
| `call_id` | UUID | FK → calls, optional | The call in which the agent opened the ticket (NULL for tickets made at the desk or before the agent existed) |
| `request_type` | VARCHAR(25) | required, one of: Room Service, Booking Inquiry, Housekeeping, Late Checkout, Modification Request, Airport Transfer, General Inquiry, Cancellation Request, Complaint, Extra Bed, Early Check-in, Payment Inquiry, Maintenance, Special Request, Discount Request, Staff Callback, Emergency | Type; Maintenance = something broken in the room (AC, light, tap); Special Request = a wish for a stay (celebration, dietary need...), decided by staff; a Discount Request is decided by the admin (approved: a personal one-time code is emailed); Staff Callback = the guest asked for a person and no one was free; Emergency = raised by the agent during an emergency |
| `category` | VARCHAR(25) | optional, see the table rules | Complaint: Room Issue, Service Issue, Facility Issue, Billing Issue or Booking Issue (NULL = not said). Special Request: Checkout Extension, Service Request, Celebration Arrangement, Dietary Requirement, Transportation, Accessibility Request or Room Preference. Other types: NULL |
| `priority` | VARCHAR(8) | required, one of: Normal, Urgent, Critical, default 'Normal' | Normal; Urgent = a Staff Callback or a serious complaint; Critical = Emergency only (shown first on the staff dashboard) |
| `request_text` | TEXT | required | What the guest asked |
| `request_status` | VARCHAR(12) | required, one of: Open, In Progress, Resolved, Closed, default 'Open' | Open (no one has taken it), In Progress, Resolved (done), Closed (finished without being done: rejected, cancelled by the guest, or the stay ended) |
| `handled_by` | INTEGER | FK → user_accounts, optional | Staff or admin account that took the ticket; NULL while Open |
| `decision` | VARCHAR(8) | optional, one of: Approved, Rejected | Discount Request (decided by the administrator) or Special Request (decided by staff); NULL while waiting or when the guest cancelled |
| `decided_by` | INTEGER | FK → user_accounts, optional | Account that decided |
| `decided_at` | TIMESTAMPTZ | optional | When the decision was made |
| `issued_code_id` | VARCHAR(5) | FK → discount_codes, optional | Approved Discount Request: the personal one-time code emailed to the guest |
| `created_at` | TIMESTAMPTZ | required, default now() | When it was made |
| `resolved_at` | TIMESTAMPTZ | optional | When it was Resolved or Closed (set only then) |

Table rules:
- `CHECK (customer_id IS NOT NULL OR (call_id IS NOT NULL AND request_type IN ('Emergency', 'Staff Callback')))`
- `CHECK (request_type <> 'Special Request' OR booking_id IS NOT NULL)`
- `CHECK` category: a Complaint's category is NULL or one of its five; a Special Request needs one of its seven; other types have none
- `CHECK ((request_type = 'Emergency') = (priority = 'Critical'))`
- `CHECK (request_type <> 'Staff Callback' OR priority = 'Urgent')`
- `CHECK (priority <> 'Urgent' OR request_type IN ('Staff Callback', 'Complaint'))`
- `CHECK ((request_status = 'Open') = (handled_by IS NULL))`
- `CHECK ((request_status IN ('Resolved', 'Closed')) = (resolved_at IS NOT NULL))`
- `CHECK (resolved_at IS NULL OR resolved_at >= created_at)`
- `CHECK (decision IS NULL OR request_type IN ('Discount Request', 'Special Request'))`
- `CHECK ((decision IS NULL) = (decided_at IS NULL) AND (decision IS NULL) = (decided_by IS NULL))`
- `CHECK (decision IS NULL OR request_status <> 'Open')`
- `CHECK (decided_at IS NULL OR decided_at >= created_at)`
- `CHECK ((issued_code_id IS NOT NULL) = (request_type = 'Discount Request' AND decision IS NOT DISTINCT FROM 'Approved'))`

## customer_feedback

Reviews of finished stays: one per booking.

Rows in the demo data: **4,001**

| Column | Type | Rules | Description |
|---|---|---|---|
| `feedback_id` | VARCHAR(8) | PK, required, auto: next reference | FB + 6 digits |
| `customer_id` | VARCHAR(7) | FK → customers, required | Guest |
| `booking_id` | VARCHAR(7) | FK → bookings, required, unique | Completed booking reviewed |
| `feedback_category` | VARCHAR(20) | required, one of: Room, Booking, Staff, Facilities, Service, Overall Experience, Food, Payment, Location, Cleanliness | What the review is about |
| `rating` | SMALLINT | required, rating BETWEEN 1 AND 5 | 1-5 stars |
| `sentiment` | VARCHAR(8) | required, one of: Positive, Neutral, Negative | From the rating: 4-5 Positive, 3 Neutral, 1-2 Negative |
| `feedback_text` | TEXT | required | Review text |
| `feedback_channel` | VARCHAR(12) | required, one of: Mobile App, Website, In-Hotel, Email, Survey, Voice Agent | Where it was given |
| `would_recommend` | VARCHAR(5) | required, one of: Yes, Maybe, No | Would recommend the hotel |

Table rules:
- `CHECK ((rating >= 4 AND sentiment = 'Positive') OR (rating = 3 AND sentiment = 'Neutral') OR (rating <= 2 AND sentiment = 'Negative'))`

## user_accounts

One login for everyone: guests (linked to a customer), hotel staff and admins. The demo data has 1 admin, 4 staff and an account for every customer who booked on the website, the app or with the voice agent, plus a few phone and agency guests who signed up later; the demo password of all of them is `NilePearl@2026`.

Rows in the demo data: **5,599**

| Column | Type | Rules | Description |
|---|---|---|---|
| `account_id` | SERIAL | PK, required | Account id |
| `role` | VARCHAR(5) | required, one of: Guest, Staff, Admin | Guest, Staff or Admin |
| `customer_id` | VARCHAR(7) | FK → customers, unique, optional | The guest's customer record (Guest accounts only) |
| `full_name` | VARCHAR(80) | required | Name |
| `email` | VARCHAR(120) | required, unique | Sign-in email; codes and confirmations are sent here |
| `password_hash` | TEXT | required | bcrypt hash (never the password itself) |
| `email_verified` | BOOLEAN | required, default false | Email confirmed with the code sent at sign-up |
| `is_active` | BOOLEAN | required, default true | Can sign in |
| `created_at` | TIMESTAMPTZ | required, default now() | Created |
| `last_login_at` | TIMESTAMPTZ | optional | Last sign-in |

Table rules:
- `CHECK ((role = 'Guest') = (customer_id IS NOT NULL))`

## booking_links

Bookings made elsewhere (phone, agency, booking platform) that a guest added to the account after the reference check.

Rows in the demo data: **21**

| Column | Type | Rules | Description |
|---|---|---|---|
| `account_id` | INTEGER | PK, FK → user_accounts, required | Guest account |
| `booking_id` | VARCHAR(7) | PK, FK → bookings, required | Booking added |
| `linked_at` | TIMESTAMPTZ | required, default now() | When it was added |

## verification_codes

One-time codes sent by email to confirm the email at sign-up or to reset a password. Only a hash of the code is stored. Filled by the API. Staff passwords are reset by the administrator, not with a code.

Rows in the demo data: **0**

| Column | Type | Rules | Description |
|---|---|---|---|
| `code_id` | BIGSERIAL | PK, required | Code record id |
| `account_id` | INTEGER | FK → user_accounts, required | Account the code was sent to |
| `purpose` | VARCHAR(14) | required, one of: verify_email, reset_password | verify_email (sign-up) or reset_password |
| `code_hash` | TEXT | required | Hash of the 6-digit code (never the code itself) |
| `attempts` | SMALLINT | required, 0-5, default 0 | Wrong tries so far; the code stops working after app_settings.otp_max_attempts |
| `expires_at` | TIMESTAMPTZ | required | Code expiry (app_settings.otp_valid_minutes after it was sent) |
| `used_at` | TIMESTAMPTZ | optional | When it was used; a code works only once |
| `created_at` | TIMESTAMPTZ | required, default now() | When it was sent |

Table rules:
- `CHECK (expires_at > created_at)`
- `CHECK (used_at IS NULL OR used_at >= created_at)`

## hotel_photos

Photos of the hotel areas (pool, spa, gym, restaurant, lobby, building) that the agent can show during a call. Room photos are in room_types.

Rows in the demo data: **6**

| Column | Type | Rules | Description |
|---|---|---|---|
| `photo_key` | VARCHAR(20) | PK, required | Short name of the area: hotel, lobby, pool, spa, gym, restaurant |
| `title_en` | VARCHAR(40) | required | Title in English |
| `title_ar` | VARCHAR(40) | required | Title in Arabic |
| `image_path` | VARCHAR(80) | required, unique, under /static/hotel/ | Path of the photo |
| `service_id` | VARCHAR(4) | FK → services, optional | Related priced service, if any (spa S005, gym S006) |

## calls

One row per conversation with the voice agent (voice or text). Filled by the API; shown on the dashboard. The demo data has 17 sample calls (14-19 September 2026) that agree with the rest of the data: the bookings, tickets, codes and the booking link they created.

Rows in the demo data: **17**

| Column | Type | Rules | Description |
|---|---|---|---|
| `call_id` | UUID | PK, required, default gen_random_uuid() | Call id |
| `channel` | VARCHAR(5) | required, one of: voice, text, default 'voice' | Voice call or typed chat |
| `language` | VARCHAR(16) | optional, one of: Arabic-Egyptian, Arabic, English, French, Russian | Caller's language |
| `account_id` | INTEGER | FK → user_accounts, optional | Logged-in guest account that made the call; NULL = a visitor (general answers only) |
| `customer_id` | VARCHAR(7) | FK → customers, optional | The logged-in guest's customer record (from the account); NULL for a visitor |
| `booking_id` | VARCHAR(7) | FK → bookings, optional | Main booking discussed (one in the account, or one added to it with link_booking) |
| `status` | VARCHAR(10) | required, one of: active, completed, escalated, abandoned, default 'active' | Call status |
| `escalation_reason` | TEXT | optional | Why it was handed to a person |
| `assigned_staff_id` | INTEGER | FK → user_accounts, optional | Staff account that took the escalated call |
| `summary` | TEXT | optional | Short summary for the dashboard |
| `started_at` | TIMESTAMPTZ | required, default now() | Start |
| `ended_at` | TIMESTAMPTZ | optional | End |

Table rules:
- `CHECK (ended_at IS NULL OR ended_at >= started_at)`
- `CHECK (status <> 'escalated' OR escalation_reason IS NOT NULL)`

## call_messages

Every turn of every call: what the guest said (after speech-to-text) and what the agent answered.

Rows in the demo data: **90**

| Column | Type | Rules | Description |
|---|---|---|---|
| `message_id` | BIGSERIAL | PK, required | Message id |
| `call_id` | UUID | FK → calls, required | Call |
| `turn_no` | INTEGER | required, turn_no >= 1 | Order within the call |
| `role` | VARCHAR(6) | required, one of: guest, agent, staff, system | Who spoke |
| `content` | TEXT | required | Text of the turn |
| `latency_ms` | INTEGER | optional, latency_ms >= 0 | Agent turns: time from the end of the guest turn to the first audio |
| `created_at` | TIMESTAMPTZ | required, default now() | Time |

Table rules:
- `UNIQUE (call_id, turn_no)`

## call_actions

What the agent did during a call: each tool it ran (availability check, booking lookup, cancellation...) and the result.

Rows in the demo data: **22**

| Column | Type | Rules | Description |
|---|---|---|---|
| `action_id` | BIGSERIAL | PK, required | Action id |
| `call_id` | UUID | FK → calls, required | Call |
| `tool_name` | VARCHAR(40) | required | Tool, e.g. check_availability, quote_cancellation |
| `arguments` | JSONB | required, default '{}' | Tool input |
| `result` | JSONB | optional | Tool output |
| `success` | BOOLEAN | required | Did it succeed |
| `booking_id` | VARCHAR(7) | FK → bookings, optional | Booking created, changed or read |
| `created_at` | TIMESTAMPTZ | required, default now() | Time |

## Functions and views

| Name | What it does |
|---|---|
| `hotel_today()` | The dataset's "today" (`app_settings.system_date`) |
| `free_rooms(room_type, check_in, check_out)` | Free rooms of a type for the nights [check_in, check_out); Nile view first |
| `trg_booking_capacity` (trigger) | Refuses a booking whose adults + children exceed the room type capacity |
| `v_booking_details` | One row per booking with guest, room, type, discount, amount due, check-in/out and payment: what the guest may hear about a booking in the account |
| `v_call_overview` | Dashboard list of calls: visitor or account, turns, actions, tickets opened, average latency and duration |
