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
-- 2. find_booking(booking_ref, last_name | phone_last4) - identity check built in:
--    no row comes back unless the reference AND (last name in English or Arabic, or phone digits) match.
---------------------------------------------------------------------------------------------------
SELECT booking_id, booking_status, rate_plan, check_in, check_out, nights, adults, children,
       room_type_name, room_number, view, price_per_night, total_amount,
       payment_method, payment_status, amount_paid, refund_amount,
       first_name, last_name, first_name_ar, last_name_ar
FROM v_booking_details
WHERE booking_id = upper(:booking_ref)
  AND (lower(last_name) = lower(:last_name) OR last_name_ar = :last_name OR phone_last4 = :phone_last4);

---------------------------------------------------------------------------------------------------
-- 3. quote_cancellation(booking_ref, ...) - what cancelling now costs. Changes nothing.
--    Flexible: free until 48 h before 3:00 PM on the arrival day, then the first night.
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
  WHERE booking_id = upper(:booking_ref) AND booking_status = 'Confirmed' AND check_in > hotel_today()
) q;

-- 3b. cancel after the guest said yes (one transaction). The payment row is then updated by the
--     API from the quote above: refund = amount_paid - charge (see docs/BUSINESS_RULES.md, payments).
UPDATE bookings SET booking_status = 'Cancelled', cancelled_at = now()
WHERE booking_id = upper(:booking_ref) AND booking_status = 'Confirmed'
RETURNING booking_id, booking_status;

---------------------------------------------------------------------------------------------------
-- 4. create_booking - after availability and the guest's "yes". booking_id, nights and total are
--    filled by the database; the exclusion constraint refuses a room that was taken meanwhile.
---------------------------------------------------------------------------------------------------
INSERT INTO bookings (customer_id, room_number, room_type_id, check_in, check_out, adults, children,
                      booking_status, booking_channel, rate_plan, price_per_night, created_at)
VALUES (:customer_id, :room_number, :room_type_id, :check_in, :check_out, :adults, :children,
        'Confirmed', 'Voice Agent', :rate_plan, :price_per_night, now())
RETURNING booking_id, nights, total_amount;

INSERT INTO payments (booking_id, payment_method, payment_status, created_at)
VALUES (:booking_id, :payment_method, 'Pending', now())
RETURNING payment_id;

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
