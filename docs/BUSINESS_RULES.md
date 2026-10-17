# Business rules

The rules every part of the system follows. The knowledge base states them to guests; the
database and the API enforce them. Prices are in EGP and include 12% service, 14% VAT and 1% city tax.

## Rooms and capacity
- 150 rooms on floors 2-16; `room_number = floor x 100 + n`. Rooms 1-5 of each floor and every Suite face the Nile.
- Capacity: Single 1, Double 2, Twin 2, Deluxe 3, Family 4, Suite 4. **Children count toward capacity.**
  An extra bed (2,500 EGP/night) does not raise capacity. A party of 5+ needs two rooms. *(DB: trigger `trg_booking_capacity`)*

## Bookings
- Statuses: **Pending** (booked, waiting for the payment link; the room is held), **Confirmed** (paid; upcoming
  or in progress), **Completed** (stayed and left), **Cancelled**, **No-show**.
- Payment hold: a new booking is Pending until its payment link is paid (Flexible: the first-night deposit;
  Non-refundable: the total). The link is valid **24 hours**, or **2 hours** when arrival is less than 24 hours
  away (`app_settings.deposit_hold_hours`, `deposit_hold_hours_last_minute`; deadline in `payments.payment_due_at`).
  Paid in time: the booking becomes Confirmed. Not paid: it is cancelled automatically, the payment becomes
  **Expired** and the room is released. A declined card does not extend the deadline; the agent can resend the link.
- Only Pending, Confirmed and Completed bookings occupy a room. Two of them can never share a room on the
  same night. *(DB: exclusion constraint `no_double_booking`)*
- Nights are `[check_in, check_out)`: a guest leaving on the 10th and another arriving on the 10th
  is allowed (back-to-back).
- Relative to `system_date`: Completed has `check_out <= today`; Confirmed has `check_out >= today`;
  No-show has `check_in < today` (a reservation is held until 23:59 on the arrival day).
- `nights` and `total_amount = price_per_night x nights` are computed by the database.
- A booking's room must be of the booked room type. *(DB: composite foreign key)*

## Rate plans, cancellation, refunds
| | Flexible | Non-refundable |
|---|---|---|
| Price | standard rate | 15% lower |
| Payment | first night online as a deposit (payment link), the rest at the hotel | full amount at booking |
| Cancel 48 h+ before 3 PM on arrival day | free: the deposit is refunded | nothing refunded |
| Cancel later or no-show | first night charged: the deposit is kept, nothing more | nothing refunded |
| Change dates or room | free until 48 h before arrival | not allowed |

- Refunds are processed within 3 business days; card refunds appear 7-14 business days later.
- Leaving earlier than booked without telling reception at check-in: one extra night is charged.

## Payments (one per booking)
| Booking status | Allowed payment status |
|---|---|
| Pending | Pending, Failed (a declined attempt; the deadline does not move) |
| Confirmed | Paid, Partially Refunded |
| Completed | Paid, Partially Refunded |
| Cancelled | Paid (nothing refunded), Refunded, Partially Refunded, Failed, Expired (link not paid in time) |
| No-show | Paid (the deposit is kept), Refunded, Partially Refunded |

`amount_paid` is what was collected: for a Flexible booking the first-night deposit (`price_per_night`)
until the stay is Completed, then the booking total (the rest is paid at the hotel); for a
Non-refundable booking the total. It is 0 when nothing was collected (Pending, Failed). `refund_amount` equals `amount_paid` for Refunded, is between 0 and it for
Partially Refunded, and is 0 otherwise. *(checked by `database/tests/run_checks.sql`)*

## Check-in and check-out
- Check-in 3:00 PM; free from 12:00 PM if a room is ready; before 12:00 PM: 50% of the night.
- Check-out 12:00 PM; until 4:00 PM: 1,500 EGP; until 6:00 PM: 50% of the night; later: a full night.
  Loyalty members get it free until 1 PM (Silver), 2 PM (Gold), 4 PM (Platinum), subject to availability.
- Deposit at check-in: 3,000 EGP per night, released at check-out.
- ID: Egyptians national ID or passport, foreigners passport. The guest checking in is 18+.

## Children
Under 6: free, breakfast included. 6-11: breakfast 600 EGP. 12+: adult prices. Baby cot free.

## Loyalty (Nile Pearl Rewards)
Silver 10 / Gold 25 / Platinum 50 nights in a calendar year. 1 point per 10 EGP plus a tier
bonus (20 / 50 / 100%). 1,000 points = 500 EGP. Points expire after 24 months without activity
and cannot be transferred. Member rate: 15% off. **One discount per booking.**

## Discount codes
Valid only between `start_date` and `end_date` and below `max_usage` (NULL = unlimited).
`status` on `system_date`: Expired, then Scheduled, then Exhausted, otherwise Active.
- The agent applies only the extended-stay discount (7+ nights, 12%) or a valid code, whichever is bigger, and only
  on the Flexible rate: Non-refundable is already 15% less and takes no other discount (the database refuses it).
  Member, corporate, group and low-season rates are arranged by the reservations team. Any other
  discount is a `Discount Request` (customer_requests) decided by the admin; if approved, a code is emailed.

## Guest service
- Every ticket is a row of `customer_requests` (query 10): in-stay requests, `Maintenance`, `Complaint` (category:
  Room, Service, Facility, Billing or Booking Issue), `Special Request` (needs a booking and a category; staff approve
  or reject it), `Discount Request` (the admin decides), `Staff Callback`, `Emergency`. Tickets need a logged-in guest,
  except an `Emergency` or `Staff Callback` from a visitor, which is kept with the call (`call_id`).
- Status: Open (no one has it) → In Progress (`handled_by`) → Resolved (done) or Closed (not done: rejected,
  cancelled, or the stay ended); `resolved_at` only then. Priority: Critical = Emergency only; Urgent = Staff Callback
  or a serious complaint; otherwise Normal.
- The staff queue holds only tickets that can still be acted on: from the last 14 days, or a service for a stay
  that is on or coming. A service for a stay (housekeeping, room service, special request...) ends with the stay.
- Talking to a person: only when the guest has a problem and asks. It continues as a live chat with a free
  staff member (`calls.assigned_staff_id`, `call_messages.role = 'staff'`); if no one is free, a `Staff Callback`
  ticket with priority Urgent is opened and staff contact the guest in the chat or by email.
- Emergencies: the agent gives reception +20 2 2794 5500 and ambulance 123, police 122, fire 180, and opens an
  `Emergency` ticket with priority Critical, shown first on the staff dashboard.
- Tickets and feedback that name a booking belong to the guest who holds it.
- Room, service and facility complaints belong to a stay that has started (after check-in).
- Check-in and check-out are recorded by staff (`checked_in_at`, `checked_out_at`, query 8). A room is Occupied
  while a guest is checked in; a Completed stay has both times.
- Feedback exists only for Completed stays, one per booking; rating 4-5 Positive, 3 Neutral, 1-2 Negative.

## Identity and privacy
- Accounts: one login for guests, staff and admins (`user_accounts`). Visitors who are not logged in get
  general answers only; booking, managing a booking and requests need a login.
- A logged-in guest sees the bookings of the account (`v_account_bookings`): those under the account's
  customer plus those linked to it, with no further questions. Any other booking is never discussed.
- A booking made by phone, agency or booking platform is added once (`booking_links`) after the check:
  booking reference **and** last name (English or Arabic spelling) **or** the last 4 phone digits.
  Customer service uses the same check by phone and email.
- The agent never asks for card numbers or security codes. Data deletion requests go to a person.

## "Today"
The demo data is a snapshot on **2026-09-19** (`app_settings.system_date`, `hotel_today()`).
Statuses, room occupancy and code validity are correct for that date. Use it instead of the clock.
