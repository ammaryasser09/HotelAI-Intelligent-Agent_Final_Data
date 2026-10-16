-- Nile Pearl Hotel - the queries the API needs, one per agent tool / dashboard screen.
-- Parameters are written :name (SQLAlchemy text() style). With psycopg use %(name)s instead.
-- "Today" is hotel_today() (app_settings.system_date), never now()::date, while the demo data is in use.

---------------------------------------------------------------------------------------------------
-- 1. check_availability(room_type, check_in, check_out, guests)
--    The API first validates: check_out > check_in, check_in >= hotel_today(), guests <= capacity.
---------------------------------------------------------------------------------------------------
-- 1a. room type, capacity and standard price
SELECT room_type_id, room_type_name, capacity, base_price
FROM room_types
WHERE room_type_id = upper(:room_type) OR lower(room_type_name) = lower(:room_type);

-- 1b. free rooms (Nile view first)
SELECT room_number, floor, view FROM free_rooms(:room_type, :check_in, :check_out);

-- 1c. when nothing is free: every other type that fits the guests and has a free room
SELECT t.room_type_name, t.capacity, t.base_price, count(f.room_number) AS rooms_free
FROM room_types t
CROSS JOIN LATERAL free_rooms(t.room_type_id, :check_in, :check_out) f
WHERE t.capacity >= :guests
GROUP BY t.room_type_id, t.room_type_name, t.capacity, t.base_price
ORDER BY t.base_price;

---------------------------------------------------------------------------------------------------
-- 2. my_bookings(account_id) - a logged-in guest sees the bookings of the account, no extra questions
---------------------------------------------------------------------------------------------------
SELECT d.*, ab.access
FROM v_account_bookings ab JOIN v_booking_details d USING (booking_id)
WHERE ab.account_id = :account_id
ORDER BY d.check_in DESC;

---------------------------------------------------------------------------------------------------
-- 2b. link_booking(account_id, booking_ref, last_name | phone_last4) - a booking made by phone, agency
--     or a booking platform is added to the account once. Check first (query below), then insert.
--     No row comes back unless the reference AND (last name in English or Arabic, or phone digits) match.
---------------------------------------------------------------------------------------------------
SELECT booking_id, booking_status, rate_plan, check_in, check_out, nights, adults, children,
       room_type_name, room_number, view, price_per_night, total_amount,
       payment_method, payment_status, amount_paid, refund_amount, payment_due_at,
       first_name, last_name, first_name_ar, last_name_ar
FROM v_booking_details
WHERE booking_id = upper(:booking_ref)
  AND (lower(last_name) = lower(:last_name) OR last_name_ar = :last_name OR phone_last4 = :phone_last4);

INSERT INTO booking_links (account_id, booking_id) VALUES (:account_id, upper(:booking_ref))
ON CONFLICT DO NOTHING;

---------------------------------------------------------------------------------------------------
-- 3. quote_cancellation(booking_ref, ...) - what cancelling now costs. Changes nothing.
--    Flexible: free until 48 h before 3:00 PM on the arrival day (the first-night deposit is refunded),
--    then the first night (the deposit is kept). Only the deposit is collected before arrival.
--    Non-refundable: nothing is refunded. Run after the identity check in query 2.
---------------------------------------------------------------------------------------------------
SELECT booking_id, booking_status, rate_plan, total_amount, amount_paid,
       charge, greatest(amount_paid - charge, 0) AS refund
FROM (
  SELECT v.*,
         CASE WHEN rate_plan = 'Non-refundable' THEN total_amount
              WHEN (check_in + time '15:00') - (hotel_today() + time '12:00') >= interval '48 hours' THEN 0
              ELSE price_per_night END AS charge
  FROM v_booking_details v
  WHERE booking_id = upper(:booking_ref) AND booking_status IN ('Pending', 'Confirmed') AND check_in > hotel_today()
) q;

-- 3b. cancel after the guest said yes (one transaction). The refund goes back automatically through
--     the payment gateway (Paymob refund API), then the payment row records it: refund = amount_paid - charge.
UPDATE bookings SET booking_status = 'Cancelled', cancelled_at = now()
WHERE booking_id = upper(:booking_ref) AND booking_status IN ('Pending', 'Confirmed')
RETURNING booking_id, booking_status;

UPDATE payments SET refund_amount = :refund,
       payment_status = CASE WHEN :refund = 0 THEN payment_status
                             WHEN :refund = amount_paid THEN 'Refunded' ELSE 'Partially Refunded' END
WHERE booking_id = upper(:booking_ref);

---------------------------------------------------------------------------------------------------
-- 4. create_booking - after availability and the guest's "yes". booking_id, nights and total are
--    filled by the database; the exclusion constraint refuses a room that was taken meanwhile.
---------------------------------------------------------------------------------------------------
INSERT INTO bookings (customer_id, room_number, room_type_id, check_in, check_out, adults, children,
                      booking_status, booking_channel, rate_plan, price_per_night, created_at)
VALUES (:customer_id, :room_number, :room_type_id, :check_in, :check_out, :adults, :children,
        'Pending', 'Voice Agent', :rate_plan, :price_per_night, now())
RETURNING booking_id, nights, total_amount;

-- Flexible: the API then sends the payment link for the first-night deposit (price_per_night);
-- when the link is paid the row becomes Paid with amount_paid = price_per_night.
-- Non-refundable: the link is for the full total_amount.
-- The booking stays Pending (room held) until the link is paid: 24 h, or 2 h when arrival is less than
-- 24 h away (app_settings.deposit_hold_hours / deposit_hold_hours_last_minute).
INSERT INTO payments (booking_id, payment_method, payment_status, payment_due_at, created_at)
VALUES (:booking_id, :payment_method, 'Pending',
        now() + make_interval(hours => CASE WHEN (:check_in::date + time '15:00') - now() < interval '24 hours'
                                            THEN (SELECT value::int FROM app_settings WHERE key = 'deposit_hold_hours_last_minute')
                                            ELSE (SELECT value::int FROM app_settings WHERE key = 'deposit_hold_hours') END),
        now())
RETURNING payment_id, payment_due_at;

-- 4b. the payment gateway (Paymob) reports the link as paid: confirm the booking
UPDATE payments SET payment_status = 'Paid', amount_paid = :amount WHERE booking_id = upper(:booking_ref);
UPDATE bookings SET booking_status = 'Confirmed' WHERE booking_id = upper(:booking_ref) AND booking_status = 'Pending';

-- 4c. scheduled job (e.g. every 5 minutes): cancel the bookings whose link was not paid in time
--     With the demo data, compare with the frozen clock instead of now(), or the 24 demo Pending bookings expire at once.
WITH expired AS (
  UPDATE payments p SET payment_status = 'Expired'
  FROM bookings b
  WHERE b.booking_id = p.booking_id AND b.booking_status = 'Pending' AND p.payment_due_at < now()
  RETURNING p.booking_id)
UPDATE bookings SET booking_status = 'Cancelled', cancelled_at = now()
WHERE booking_id IN (SELECT booking_id FROM expired)
RETURNING booking_id;

---------------------------------------------------------------------------------------------------
-- 5. late_checkout_quote / loyalty_status
---------------------------------------------------------------------------------------------------
SELECT m.tier, m.points_balance, t.late_checkout_until,
       floor(m.points_balance / r1.value) * r2.value AS points_worth_egp
FROM bookings b
JOIN loyalty_members m ON m.customer_id = b.customer_id AND m.status = 'Active'
JOIN loyalty_tiers t ON t.tier = m.tier
CROSS JOIN (SELECT value FROM loyalty_rules WHERE rule = 'redeem_points') r1
CROSS JOIN (SELECT value FROM loyalty_rules WHERE rule = 'redeem_value') r2
WHERE b.booking_id = upper(:booking_ref);

---------------------------------------------------------------------------------------------------
-- 6. check_discount_code(code)
---------------------------------------------------------------------------------------------------
SELECT discount_code, discount_type, discount_value, status, start_date, end_date,
       CASE WHEN max_usage IS NULL THEN NULL ELSE max_usage - usage_count END AS uses_left
FROM discount_codes WHERE discount_code = upper(:code);

---------------------------------------------------------------------------------------------------
-- 7. menu / room_service_quote
---------------------------------------------------------------------------------------------------
SELECT item_id, name_en, name_ar, category, price, dietary FROM menu_items
WHERE NOT :night_only OR night_menu ORDER BY category, price;

SELECT price AS delivery_charge FROM services WHERE service_id = 'S002';

---------------------------------------------------------------------------------------------------
-- 8. Logging a call (dashboard data)
---------------------------------------------------------------------------------------------------
INSERT INTO calls (channel, language) VALUES (:channel, :language) RETURNING call_id;
INSERT INTO call_messages (call_id, turn_no, role, content, latency_ms)
VALUES (:call_id, :turn_no, :role, :content, :latency_ms);
INSERT INTO call_actions (call_id, tool_name, arguments, result, success, booking_id)
VALUES (:call_id, :tool_name, CAST(:arguments AS jsonb), CAST(:result AS jsonb), :success, :booking_id);
UPDATE calls SET status = 'escalated', escalation_reason = :reason WHERE call_id = :call_id;
UPDATE calls SET status = 'completed', ended_at = now(), summary = :summary WHERE call_id = :call_id;

---------------------------------------------------------------------------------------------------
-- 9. Dashboard
---------------------------------------------------------------------------------------------------
-- calls list (newest first)
SELECT * FROM v_call_overview ORDER BY started_at DESC LIMIT 50;
-- escalated calls waiting for a person
SELECT * FROM v_call_overview WHERE status = 'escalated' AND assigned_to IS NULL ORDER BY started_at;
-- one call: transcript and actions
SELECT turn_no, role, content, latency_ms, created_at FROM call_messages WHERE call_id = :call_id ORDER BY turn_no;
SELECT tool_name, arguments, result, success, booking_id, created_at FROM call_actions WHERE call_id = :call_id ORDER BY created_at;
-- today's numbers
SELECT count(*) AS calls,
       count(*) FILTER (WHERE status = 'escalated') AS escalated,
       round(100.0 * count(*) FILTER (WHERE status = 'completed') / nullif(count(*), 0), 1) AS resolved_pct
FROM calls WHERE started_at::date = current_date;
-- occupancy on a date
SELECT round(100.0 * count(*) / (SELECT count(*) FROM rooms), 1) AS occupancy_pct
FROM bookings WHERE booking_status IN ('Confirmed', 'Completed') AND check_in <= :on_date AND :on_date < check_out;

---------------------------------------------------------------------------------------------------
-- 8. Staff dashboard: check-in, balance and check-out (the rest of a Flexible stay is paid at the hotel)
---------------------------------------------------------------------------------------------------
-- 8a. arrivals today
SELECT booking_id, first_name, last_name, room_type_name, room_number, nights, total_amount, amount_paid,
       total_amount - amount_paid AS balance_due
FROM v_booking_details WHERE booking_status = 'Confirmed' AND check_in = hotel_today() ORDER BY room_number;

-- 8b. check-in
UPDATE bookings SET checked_in_at = now()
WHERE booking_id = upper(:booking_ref) AND booking_status = 'Confirmed' AND check_in <= hotel_today() AND checked_in_at IS NULL
RETURNING booking_id, room_number;
UPDATE rooms SET status = 'Occupied' WHERE room_number = :room_number;

-- 8c. check-out: the guest pays the balance at the desk, the stay is completed and the room freed
UPDATE payments p SET amount_paid = b.total_amount, payment_status = 'Paid', payment_method = :payment_method
FROM bookings b WHERE b.booking_id = p.booking_id AND b.booking_id = upper(:booking_ref);
UPDATE bookings SET booking_status = 'Completed', checked_out_at = now()
WHERE booking_id = upper(:booking_ref) AND booking_status = 'Confirmed'
RETURNING booking_id, room_number;
UPDATE rooms SET status = 'Available' WHERE room_number = :room_number;

---------------------------------------------------------------------------------------------------
-- 9. change_booking - after quote_modification and the guest's "yes" (one transaction). New dates or a new
--    room type may move the guest to another free room of the type; extra nights keep the same room.
--    New dates keep the agreed price_per_night; a new room type uses its base_price. The exclusion
--    constraint refuses a room that was taken meanwhile. Not for Booking Platform or Non-refundable bookings.
---------------------------------------------------------------------------------------------------
-- 9a. a free room for the new stay, ignoring this booking itself (same room first, then Nile view)
SELECT r.room_number FROM rooms r
WHERE r.room_type_id = :room_type_id AND r.status <> 'Maintenance'
  AND NOT EXISTS (SELECT 1 FROM bookings b
                  WHERE b.room_number = r.room_number AND b.booking_id <> upper(:booking_ref)
                    AND b.booking_status IN ('Pending', 'Confirmed', 'Completed')
                    AND b.check_in < :new_check_out AND :new_check_in < b.check_out)
ORDER BY (r.room_number = :current_room) DESC, (r.view = 'Nile') DESC, r.room_number
LIMIT 1;

-- 9b. apply the change
UPDATE bookings SET check_in = :new_check_in, check_out = :new_check_out, room_type_id = :room_type_id,
       room_number = :room_number, adults = :adults, children = :children, price_per_night = :price_per_night
WHERE booking_id = upper(:booking_ref) AND booking_status IN ('Pending', 'Confirmed') AND rate_plan = 'Flexible'
RETURNING booking_id, check_in, check_out, room_number, nights, total_amount;

---------------------------------------------------------------------------------------------------
-- 10. create_request - a request, complaint or emergency raised by the agent becomes a ticket for the staff
--     (housekeeping, maintenance, room service, extra bed, Discount Request, Staff Callback, Emergency...)
---------------------------------------------------------------------------------------------------
INSERT INTO customer_requests (customer_id, booking_id, request_type, request_text, request_status, priority, created_at)
VALUES (:customer_id, :booking_id, :request_type, :request_text, 'Open',
        CASE :request_type WHEN 'Emergency' THEN 'Critical' WHEN 'Staff Callback' THEN 'Urgent' ELSE 'Normal' END, now())
RETURNING request_id, priority;

-- 10b. staff queue: open tickets, emergencies first
SELECT request_id, priority, request_type, request_text, customer_id, booking_id, created_at
FROM customer_requests WHERE request_status IN ('Open', 'In Progress')
ORDER BY CASE priority WHEN 'Critical' THEN 0 WHEN 'Urgent' THEN 1 ELSE 2 END, created_at;

-- 10c. handoff: the guest asked for a person. Assign a free staff member to the call (live chat);
--      when nobody is free the API opens a Staff Callback ticket (10) instead.
UPDATE calls SET status = 'escalated', escalation_reason = :reason, assigned_staff_id = :staff_account_id
WHERE call_id = :call_id;
