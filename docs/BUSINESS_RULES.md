# Business rules

The rules every part of the system follows. The knowledge base states them to guests; the
database and the API enforce them. Prices are in EGP and include 12% service, 14% VAT and 1% city tax.

## Rooms and capacity
- 150 rooms on floors 2-16; `room_number = floor x 100 + n`. Rooms 1-5 of each floor and every Suite face the Nile.
- Capacity: Single 1, Double 2, Twin 2, Deluxe 3, Family 4, Suite 4. **Children count toward capacity.**
  An extra bed (2,500 EGP/night) does not raise capacity. A party of 5+ needs two rooms. *(DB: trigger `trg_booking_capacity`)*

## Bookings
- Statuses: **Confirmed** (upcoming or in progress), **Completed** (stayed and left), **Cancelled**, **No-show**.
- Only Confirmed and Completed bookings occupy a room. Two of them can never share a room on the
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
| Payment | card guarantee, pay at the hotel | full amount at booking |
| Cancel 48 h+ before 3 PM on arrival day | free | nothing refunded |
| Cancel later or no-show | first night charged, rest refunded | nothing refunded |
| Change dates or room | free until 48 h before arrival | not allowed |

- Refunds are processed within 3 business days; card refunds appear 7-14 business days later.
- Leaving earlier than booked without telling reception at check-in: one extra night is charged.

## Payments (one per booking)
| Booking status | Allowed payment status |
|---|---|
| Confirmed | Paid, Pending, Failed, Partially Refunded |
| Completed | Paid, Partially Refunded |
| Cancelled / No-show | Paid (nothing refunded), Refunded, Partially Refunded, Failed |

`amount_paid` equals the booking total whenever money was collected and 0 when it was not
(Pending, Failed). `refund_amount` equals `amount_paid` for Refunded, is between 0 and it for
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

## Guest service
- Requests, complaints, special requests and feedback that name a booking belong to the guest who holds it.
- Room, service and facility complaints belong to a stay that happened. `resolved_at` is set only for Resolved/Closed.
- A special request is Fulfilled only for a stay that happened; only Fulfilled requests have `fulfilled_at`.
- Feedback exists only for Completed stays, one per booking; rating 4-5 Positive, 3 Neutral, 1-2 Negative.

## Identity and privacy
Before discussing, changing or cancelling a booking: booking reference **and** last name (English
or Arabic spelling) **or** the last 4 phone digits. The agent never asks for card numbers or
security codes. Data deletion requests go to a person.

## "Today"
The demo data is a snapshot on **2026-09-19** (`app_settings.system_date`, `hotel_today()`).
Statuses, room occupancy and code validity are correct for that date. Use it instead of the clock.
