-- Nile Pearl Hotel - the queries the API needs, one per agent tool / dashboard screen.
-- Parameters are written :name (SQLAlchemy text() style). With psycopg use %(name)s instead.
-- "Today" is hotel_today() (app_settings.system_date), never now()::date, while the demo data is in use.

---------------------------------------------------------------------------------------------------
-- 1. check_availability(room_type, check_in, check_out, guests)
--    The API first validates: check_out > check_in, check_in >= hotel_today(), guests <= capacity.
---------------------------------------------------------------------------------------------------
-- 1a. room type, capacity, standard price and photos (Nile and city view; the Suite has a Nile photo only)
SELECT room_type_id, room_type_name, capacity, base_price, image_nile, image_city
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
SELECT booking_id, booking_status, rate_plan, amount_due, amount_paid,
       charge, greatest(amount_paid - charge, 0) AS refund
FROM (
  SELECT v.*,
         CASE WHEN rate_plan = 'Non-refundable' THEN amount_due
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
--    One discount at most, Flexible rate only: the Long Stay discount (7+ nights, pricing_tiers 'Extended Stay':
--    total x 0.12) or a valid code (query 6), the bigger of the two. Non-refundable is already the special price:
--    no other discount (the database refuses it). Leave discount_source / discount_code_id NULL and discount_amount 0 when none.
INSERT INTO bookings (customer_id, room_number, room_type_id, check_in, check_out, adults, children,
                      booking_status, booking_channel, rate_plan, price_per_night,
                      discount_source, discount_code_id, discount_amount, created_at)
VALUES (:customer_id, :room_number, :room_type_id, :check_in, :check_out, :adults, :children,
        'Pending', 'Voice Agent', :rate_plan, :price_per_night,
        :discount_source, :discount_code_id, coalesce(:discount_amount, 0), now())
RETURNING booking_id, nights, total_amount, discount_amount, amount_due;

-- A code was used: count it (a personal code becomes Exhausted after its one use).
UPDATE discount_codes SET usage_count = usage_count + 1,
       status = CASE WHEN max_usage IS NOT NULL AND usage_count + 1 >= max_usage THEN 'Exhausted' ELSE status END
WHERE code_id = :discount_code_id;

-- Flexible: the API then sends the payment link for the deposit: price_per_night x app_settings.deposit_nights
-- (1 night); when the link is paid the row becomes Paid with amount_paid = the deposit. The rest of amount_due
-- is paid at the hotel. Non-refundable: the link is for the full amount_due.
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
--    A personal code (customer_id set) works only for its own guest: pass the logged-in guest's customer_id.
SELECT code_id, discount_code, discount_type, discount_value, status, start_date, end_date,
       CASE WHEN max_usage IS NULL THEN NULL ELSE max_usage - usage_count END AS uses_left,
       (customer_id IS NULL OR customer_id = :customer_id) AS usable_by_this_guest
FROM discount_codes WHERE discount_code = upper(:code);

---------------------------------------------------------------------------------------------------
-- 7. menu / room_service_quote
---------------------------------------------------------------------------------------------------
SELECT item_id, name_en, name_ar, category, price, dietary FROM menu_items
WHERE NOT :night_only OR night_menu ORDER BY category, price;

SELECT price AS delivery_charge FROM services WHERE service_id = 'S002';

---------------------------------------------------------------------------------------------------
-- 8. Staff dashboard: check-in, balance and check-out (the rest of a Flexible stay is paid at the hotel)
---------------------------------------------------------------------------------------------------
-- 8a. arrivals still to check in today
SELECT booking_id, first_name, last_name, room_type_name, room_number, nights, amount_due, amount_paid,
       amount_due - amount_paid AS balance_due
FROM v_booking_details WHERE booking_status = 'Confirmed' AND check_in <= hotel_today() AND checked_in_at IS NULL ORDER BY room_number;

-- 8b. check-in
UPDATE bookings SET checked_in_at = now()
WHERE booking_id = upper(:booking_ref) AND booking_status = 'Confirmed' AND check_in <= hotel_today() AND checked_in_at IS NULL
RETURNING booking_id, room_number;
UPDATE rooms SET status = 'Occupied' WHERE room_number = :room_number;

-- 8c. check-out: the guest pays the balance at the desk, the stay is completed and the room freed
UPDATE payments p SET amount_paid = b.amount_due, payment_status = 'Paid', payment_method = :payment_method
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
--     (housekeeping, maintenance, room service, Complaint / Special Request with a category, Discount Request,
--     Staff Callback, Emergency...). customer_id comes from the login; a visitor who is not logged in can only
--     raise an Emergency (or a Staff Callback), with customer_id NULL and the call_id.
---------------------------------------------------------------------------------------------------
INSERT INTO customer_requests (customer_id, booking_id, call_id, request_type, category, request_text, priority)
VALUES (:customer_id, :booking_id, :call_id, :request_type, :category, :request_text,
        CASE :request_type WHEN 'Emergency' THEN 'Critical' WHEN 'Staff Callback' THEN 'Urgent' ELSE 'Normal' END)
RETURNING request_id, priority;

-- 10b. staff queue: open tickets, emergencies first
SELECT r.request_id, r.priority, r.request_type, r.category, r.request_status, r.request_text, r.customer_id, r.booking_id,
       r.call_id, h.full_name AS handled_by, r.created_at
FROM customer_requests r LEFT JOIN user_accounts h ON h.account_id = r.handled_by
WHERE r.request_status IN ('Open', 'In Progress')
ORDER BY CASE r.priority WHEN 'Critical' THEN 0 WHEN 'Urgent' THEN 1 ELSE 2 END, r.created_at;

-- 10c. handoff: the guest asked for a person. Assign a free staff member to the call (live chat);
--      when nobody is free the API opens a Staff Callback ticket (10) instead.
UPDATE calls SET status = 'escalated', escalation_reason = :reason, assigned_staff_id = :staff_account_id
WHERE call_id = :call_id;

-- 10d. a member of staff takes a ticket
UPDATE customer_requests SET request_status = 'In Progress', handled_by = :staff_account_id
WHERE request_id = :request_id AND request_status = 'Open';

-- 10e. done (Resolved) or finished without being done (Closed)
UPDATE customer_requests SET request_status = :new_status, resolved_at = now(), handled_by = coalesce(handled_by, :staff_account_id)
WHERE request_id = :request_id AND request_status IN ('Open', 'In Progress') AND :new_status IN ('Resolved', 'Closed');

-- 10f. Special Request: staff approve (then it is In Progress until done, 10e) or reject it
UPDATE customer_requests SET decision = :decision, decided_by = :staff_account_id, decided_at = now(),
       handled_by = :staff_account_id,
       request_status = CASE :decision WHEN 'Approved' THEN 'In Progress' ELSE 'Closed' END,
       resolved_at = CASE :decision WHEN 'Approved' THEN NULL ELSE now() END
WHERE request_id = :request_id AND request_type = 'Special Request' AND decision IS NULL;

---------------------------------------------------------------------------------------------------
-- 11. Discount Request: the administrator decides (dashboard). The request was opened by the agent (query 10).
---------------------------------------------------------------------------------------------------
-- 11a. waiting requests
SELECT request_id, customer_id, booking_id, request_text, created_at
FROM customer_requests WHERE request_type = 'Discount Request' AND decision IS NULL ORDER BY created_at;

-- 11b. approve (one transaction): a personal one-time code for this guest, then the API emails it.
INSERT INTO discount_codes (code_id, discount_code, discount_type, discount_value, usage_count, max_usage,
                            start_date, end_date, status, customer_id)
VALUES (:code_id, upper(:discount_code), :discount_type, :discount_value, 0, 1,
        hotel_today(), hotel_today() + 30, 'Active', :customer_id)
RETURNING code_id, discount_code;

UPDATE customer_requests SET decision = 'Approved', decided_by = :admin_account_id, decided_at = now(),
       issued_code_id = :code_id, request_status = 'Resolved', handled_by = :admin_account_id, resolved_at = now()
WHERE request_id = :request_id AND request_type = 'Discount Request' AND decision IS NULL;

-- 11c. reject
UPDATE customer_requests SET decision = 'Rejected', decided_by = :admin_account_id, decided_at = now(),
       request_status = 'Closed', handled_by = :admin_account_id, resolved_at = now()
WHERE request_id = :request_id AND request_type = 'Discount Request' AND decision IS NULL;

---------------------------------------------------------------------------------------------------
-- 12. Email codes: confirm the email at sign-up, reset a forgotten password (guests only;
--     staff passwords are reset by the administrator). Store only a hash of the 6-digit code.
---------------------------------------------------------------------------------------------------
-- 12a. send a code (the API emails the plain code and keeps only its hash)
INSERT INTO verification_codes (account_id, purpose, code_hash, expires_at)
VALUES (:account_id, :purpose, :code_hash,
        now() + make_interval(mins => (SELECT value::int FROM app_settings WHERE key = 'otp_valid_minutes')))
RETURNING code_id, expires_at;

-- 12b. the latest code that can still be used; the API compares the hash of what the guest typed
SELECT code_id, code_hash, attempts FROM verification_codes
WHERE account_id = :account_id AND purpose = :purpose AND used_at IS NULL AND expires_at > now()
  AND attempts < (SELECT value::int FROM app_settings WHERE key = 'otp_max_attempts')
ORDER BY created_at DESC LIMIT 1;

-- 12c. wrong code
UPDATE verification_codes SET attempts = attempts + 1 WHERE code_id = :code_id;

-- 12d. right code: use it once, then confirm the email (or let the API set the new password_hash)
UPDATE verification_codes SET used_at = now() WHERE code_id = :code_id AND used_at IS NULL;
UPDATE user_accounts SET email_verified = true WHERE account_id = :account_id;     -- verify_email
UPDATE user_accounts SET password_hash = :new_password_hash WHERE account_id = :account_id;  -- reset_password

---------------------------------------------------------------------------------------------------
-- 13. Photos the agent can show: hotel areas (room photos come with query 1a)
---------------------------------------------------------------------------------------------------
SELECT photo_key, title_en, title_ar, image_path FROM hotel_photos
WHERE :photo_key IS NULL OR photo_key = :photo_key ORDER BY photo_key;

---------------------------------------------------------------------------------------------------
-- 14. Logging a call (dashboard data). account_id = the logged-in guest, NULL for a visitor.
---------------------------------------------------------------------------------------------------
INSERT INTO calls (channel, language, account_id, customer_id)
VALUES (:channel, :language, :account_id, (SELECT customer_id FROM user_accounts WHERE account_id = :account_id))
RETURNING call_id;
INSERT INTO call_messages (call_id, turn_no, role, content, latency_ms)
VALUES (:call_id, :turn_no, :role, :content, :latency_ms);
INSERT INTO call_actions (call_id, tool_name, arguments, result, success, booking_id)
VALUES (:call_id, :tool_name, CAST(:arguments AS jsonb), CAST(:result AS jsonb), :success, :booking_id);
UPDATE calls SET status = 'escalated', escalation_reason = :reason WHERE call_id = :call_id;
UPDATE calls SET status = 'completed', ended_at = now(), summary = :summary WHERE call_id = :call_id;

---------------------------------------------------------------------------------------------------
-- 15. Call dashboard
---------------------------------------------------------------------------------------------------
-- calls list (newest first)
SELECT * FROM v_call_overview ORDER BY started_at DESC LIMIT 50;
-- escalated calls waiting for a person
SELECT * FROM v_call_overview WHERE status = 'escalated' AND assigned_to IS NULL ORDER BY started_at;
-- one call: transcript, actions and the tickets it opened
SELECT turn_no, role, content, latency_ms, created_at FROM call_messages WHERE call_id = :call_id ORDER BY turn_no;
SELECT tool_name, arguments, result, success, booking_id, created_at FROM call_actions WHERE call_id = :call_id ORDER BY created_at;
SELECT request_id, request_type, priority, request_status FROM customer_requests WHERE call_id = :call_id ORDER BY created_at;
-- today's numbers
SELECT count(*) AS calls,
       count(*) FILTER (WHERE status = 'escalated') AS escalated,
       round(100.0 * count(*) FILTER (WHERE status = 'completed') / nullif(count(*), 0), 1) AS resolved_pct
FROM calls WHERE started_at::date = hotel_today();
-- occupancy on a date
SELECT round(100.0 * count(*) / (SELECT count(*) FROM rooms), 1) AS occupancy_pct
FROM bookings WHERE booking_status IN ('Confirmed', 'Completed') AND check_in <= :on_date AND :on_date < check_out;
