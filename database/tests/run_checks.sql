-- Integrity checks on a loaded database. Run from database/:   psql -d hotelai -f tests/run_checks.sql
-- Every line must say PASS. Nothing is changed.
\pset footer off

SELECT check_name, failures, CASE WHEN failures = 0 THEN 'PASS' ELSE 'FAIL' END AS result FROM (
  SELECT 'no two Pending/Confirmed/Completed bookings share a room and night' AS check_name, (SELECT count(*) FROM bookings a JOIN bookings b ON a.room_number = b.room_number AND a.booking_id < b.booking_id
   AND a.booking_status IN ('Pending','Confirmed','Completed') AND b.booking_status IN ('Pending','Confirmed','Completed')
   AND a.check_in < b.check_out AND b.check_in < a.check_out) AS failures
  UNION ALL
  SELECT 'guests fit the room type (children count)' AS check_name, (SELECT count(*) FROM bookings b JOIN room_types t USING (room_type_id) WHERE b.adults + b.children > t.capacity) AS failures
  UNION ALL
  SELECT 'statuses agree with system_date' AS check_name, (SELECT count(*) FROM bookings WHERE (booking_status = 'Completed' AND check_out > hotel_today())
   OR (booking_status = 'Confirmed' AND check_out < hotel_today()) OR (booking_status = 'No-show' AND check_in >= hotel_today())
   OR (booking_status = 'Pending' AND check_in <= hotel_today())) AS failures
  UNION ALL
  SELECT 'every booking has exactly one payment' AS check_name, (SELECT count(*) FROM bookings b LEFT JOIN payments p USING (booking_id) WHERE p.payment_id IS NULL) AS failures
  UNION ALL
  SELECT 'payment status fits the booking status' AS check_name, (SELECT count(*) FROM payments p JOIN bookings b USING (booking_id) WHERE NOT (
   (b.booking_status = 'Pending' AND p.payment_status IN ('Pending','Failed'))
   OR (b.booking_status = 'Confirmed' AND p.payment_status IN ('Paid','Partially Refunded'))
   OR (b.booking_status = 'Completed' AND p.payment_status IN ('Paid','Partially Refunded'))
   OR (b.booking_status = 'Cancelled' AND p.payment_status IN ('Paid','Refunded','Partially Refunded','Failed','Expired'))
   OR (b.booking_status = 'No-show' AND p.payment_status IN ('Paid','Refunded','Partially Refunded')))) AS failures
  UNION ALL
  SELECT 'a Pending booking has a payment deadline after system_date, and only Pending bookings have one' AS check_name, (SELECT count(*) FROM payments p JOIN bookings b USING (booking_id) WHERE
   (b.booking_status = 'Pending' AND (p.payment_due_at IS NULL OR p.payment_due_at::date < hotel_today()))
   OR (b.booking_status <> 'Pending' AND p.payment_due_at IS NOT NULL)) AS failures
  UNION ALL
  SELECT 'amount paid: the amount due, or the deposit (deposit_nights) for Flexible stays not completed (0 if nothing collected)' AS check_name, (SELECT count(*) FROM payments p JOIN bookings b USING (booking_id) WHERE
   (p.payment_status IN ('Paid','Refunded','Partially Refunded') AND p.amount_paid <> CASE
      WHEN b.rate_plan = 'Flexible' AND b.booking_status <> 'Completed'
        THEN b.price_per_night * least(b.nights, (SELECT value::int FROM app_settings WHERE key = 'deposit_nights'))
      ELSE b.amount_due END)
   OR (p.payment_status IN ('Pending','Failed','Expired') AND p.amount_paid <> 0)) AS failures
  UNION ALL
  SELECT 'a Flexible deposit is refunded only for an early cancellation' AS check_name, (SELECT count(*) FROM payments p JOIN bookings b USING (booking_id)
   WHERE b.rate_plan = 'Flexible' AND b.booking_status = 'No-show' AND p.refund_amount > 0) AS failures
  UNION ALL
  SELECT 'refunds agree with the payment status' AS check_name, (SELECT count(*) FROM payments WHERE (payment_status = 'Refunded' AND refund_amount <> amount_paid)
   OR (payment_status = 'Partially Refunded' AND NOT (refund_amount > 0 AND refund_amount < amount_paid))
   OR (payment_status IN ('Paid','Pending','Failed','Expired') AND refund_amount <> 0)) AS failures
  UNION ALL
  SELECT 'Non-refundable cancellations refund nothing' AS check_name, (SELECT count(*) FROM payments p JOIN bookings b USING (booking_id)
   WHERE b.rate_plan = 'Non-refundable' AND b.booking_status IN ('Cancelled','No-show') AND p.refund_amount > 0) AS failures
  UNION ALL
  SELECT 'feedback only for finished stays' AS check_name, (SELECT count(*) FROM customer_feedback f JOIN bookings b USING (booking_id) WHERE b.booking_status <> 'Completed' OR b.check_out > hotel_today()) AS failures
  UNION ALL
  SELECT 'tickets and feedback that name a booking belong to its holder (a visitor''s emergency names none)' AS check_name, (SELECT (SELECT count(*) FROM customer_requests r JOIN bookings b USING (booking_id) WHERE r.customer_id IS DISTINCT FROM b.customer_id)
   + (SELECT count(*) FROM customer_feedback r JOIN bookings b USING (booking_id) WHERE r.customer_id <> b.customer_id)) AS failures
  UNION ALL
  SELECT 'nothing dated after system_date' AS check_name, (SELECT (SELECT count(*) FROM customer_requests
     WHERE greatest(created_at, resolved_at, decided_at)::date > hotel_today())
   + (SELECT count(*) FROM customers WHERE created_at::date > hotel_today())
   + (SELECT count(*) FROM bookings WHERE greatest(created_at, checked_in_at, checked_out_at)::date > hotel_today())
   + (SELECT count(*) FROM calls WHERE greatest(started_at, ended_at)::date > hotel_today())) AS failures
  UNION ALL
  SELECT 'guests registered before their first stay' AS check_name, (SELECT count(*) FROM customers c JOIN (SELECT customer_id, min(check_in) AS first_in FROM bookings GROUP BY 1) f
   USING (customer_id) WHERE c.created_at::date > f.first_in) AS failures
  UNION ALL
  SELECT 'booking holders are 18+ at check-in' AS check_name, (SELECT count(*) FROM bookings b JOIN customers c USING (customer_id) WHERE b.check_in < c.date_of_birth + interval '18 years') AS failures
  UNION ALL
  SELECT 'room status snapshot: Occupied = a guest is checked in now' AS check_name, (SELECT count(*) FROM rooms r WHERE (r.status = 'Occupied') <> EXISTS (SELECT 1 FROM bookings b
   WHERE b.room_number = r.room_number AND b.booking_status = 'Confirmed' AND b.checked_in_at IS NOT NULL)) AS failures
  UNION ALL
  SELECT 'check-in and check-out recorded on the right days: every Completed stay, every stay that arrived before system_date' AS check_name, (SELECT count(*) FROM bookings WHERE
   (booking_status = 'Completed' AND (checked_in_at IS NULL OR checked_out_at IS NULL))
   OR (booking_status = 'Confirmed' AND check_in < hotel_today() AND checked_in_at IS NULL)
   OR (booking_status NOT IN ('Confirmed','Completed') AND checked_in_at IS NOT NULL)
   OR checked_in_at::date <> check_in OR checked_out_at::date <> check_out) AS failures
  UNION ALL
  SELECT 'discount code status agrees with system_date' AS check_name, (SELECT count(*) FROM discount_codes WHERE status <> CASE WHEN end_date < hotel_today() THEN 'Expired'
   WHEN start_date > hotel_today() THEN 'Scheduled' WHEN max_usage IS NOT NULL AND usage_count >= max_usage THEN 'Exhausted' ELSE 'Active' END) AS failures
  UNION ALL
  SELECT 'guest accounts use the customer''s email; staff and admins have no customer record' AS check_name, (SELECT count(*) FROM user_accounts a LEFT JOIN customers c USING (customer_id)
   WHERE (a.role = 'Guest' AND a.email <> c.email) OR (a.role <> 'Guest' AND a.customer_id IS NOT NULL)) AS failures
  UNION ALL
  SELECT 'linked bookings belong to another customer and were linked by system_date' AS check_name, (SELECT count(*) FROM booking_links l JOIN user_accounts a USING (account_id) JOIN bookings b USING (booking_id)
   WHERE a.role <> 'Guest' OR b.customer_id = a.customer_id OR l.linked_at::date > hotel_today()) AS failures
  UNION ALL
  SELECT 'emergencies (only) are Critical; staff callbacks Urgent; Urgent only for callbacks and serious complaints' AS check_name, (SELECT count(*) FROM customer_requests WHERE
   (request_type = 'Emergency') <> (priority = 'Critical') OR (request_type = 'Staff Callback' AND priority <> 'Urgent')
   OR (priority = 'Urgent' AND request_type NOT IN ('Staff Callback','Complaint'))) AS failures
  UNION ALL
  SELECT 'tickets are taken and decided by staff; discount requests by the administrator' AS check_name, (SELECT count(*) FROM customer_requests r
   LEFT JOIN user_accounts h ON h.account_id = r.handled_by LEFT JOIN user_accounts d ON d.account_id = r.decided_by
   WHERE h.role = 'Guest' OR d.role = 'Guest' OR (r.request_type = 'Discount Request' AND d.role <> 'Admin')) AS failures
  UNION ALL
  SELECT 'open tickets can still be acted on: from the last 14 days, or a service for a stay that is on or coming (and ends with it)' AS check_name, (SELECT count(*) FROM customer_requests r
   LEFT JOIN bookings b USING (booking_id) WHERE r.request_status IN ('Open','In Progress') AND (
     (r.request_type IN ('Housekeeping','Room Service','Extra Bed','Late Checkout','Early Check-in','Airport Transfer','Maintenance','Special Request')
      AND b.booking_status IN ('Completed','Cancelled','No-show'))
     OR (r.created_at::date < hotel_today() - 14 AND NOT (r.request_type IN ('Housekeeping','Room Service','Extra Bed','Late Checkout',
         'Early Check-in','Airport Transfer','Maintenance','Special Request') AND coalesce(b.booking_status, '') IN ('Confirmed','Pending'))))) AS failures
  UNION ALL
  SELECT 'room, service and facility complaints belong to a stay that has started' AS check_name, (SELECT count(*) FROM customer_requests r JOIN bookings b USING (booking_id)
   WHERE r.request_type = 'Complaint' AND r.category IN ('Room Issue','Service Issue','Facility Issue')
     AND (b.checked_in_at IS NULL OR r.created_at < b.checked_in_at)) AS failures
  UNION ALL
  SELECT 'calls: the caller is the account''s guest; a ticket opened in a call is dated inside it' AS check_name, (SELECT (SELECT count(*) FROM calls c LEFT JOIN user_accounts a USING (account_id)
     WHERE c.customer_id IS DISTINCT FROM a.customer_id OR a.role <> 'Guest')
   + (SELECT count(*) FROM customer_requests r JOIN calls c USING (call_id) WHERE r.created_at NOT BETWEEN c.started_at AND c.ended_at)
   + (SELECT count(*) FROM calls WHERE (status = 'escalated') <> (escalation_reason IS NOT NULL))) AS failures
  UNION ALL
  SELECT 'loyalty members joined after registering' AS check_name, (SELECT count(*) FROM loyalty_members m JOIN customers c USING (customer_id) WHERE m.join_date < c.created_at::date) AS failures
  UNION ALL
  SELECT 'AV01 Suites free for 3 nights (count)' AS check_name, (SELECT abs((SELECT count(*) FROM free_rooms('Suite', '2026-10-03', '2026-10-06')) - 2)) AS failures
  UNION ALL
  SELECT 'AV02 Double fully booked over Christmas' AS check_name, (SELECT abs((SELECT count(*) FROM free_rooms('Double', '2026-12-24', '2026-12-27')) - 0)) AS failures
  UNION ALL
  SELECT 'AV03 back-to-back: B000006 checks out 2027-06-09; the same room is free from that day' AS check_name, (SELECT CASE WHEN EXISTS (SELECT 1 FROM free_rooms('Twin', '2027-06-09', '2027-06-10') f WHERE f.room_number = 804) THEN 0 ELSE 1 END) AS failures
  UNION ALL
  SELECT 'AV04 overlap: one night before B000006 checks out' AS check_name, (SELECT CASE WHEN EXISTS (SELECT 1 FROM free_rooms('Twin', '2027-06-08', '2027-06-10') f WHERE f.room_number = 804) THEN 1 ELSE 0 END) AS failures
  UNION ALL
  SELECT 'AV05 Cancelled booking B000102 does not block its room' AS check_name, (SELECT CASE WHEN EXISTS (SELECT 1 FROM free_rooms('Suite', '2027-05-12', '2027-05-13') f WHERE f.room_number = 1510) THEN 0 ELSE 1 END) AS failures
  UNION ALL
  SELECT 'AV06 No-show booking B003077 does not block its room' AS check_name, (SELECT CASE WHEN EXISTS (SELECT 1 FROM free_rooms('Single', '2026-06-25', '2026-06-26') f WHERE f.room_number = 309) THEN 0 ELSE 1 END) AS failures
  UNION ALL
  SELECT 'AV07 room 210 is in maintenance' AS check_name, (SELECT CASE WHEN EXISTS (SELECT 1 FROM free_rooms('Single', '2027-08-20', '2027-08-22') f WHERE f.room_number = 210) THEN 1 ELSE 0 END) AS failures
  UNION ALL
  SELECT 'one discount at most: Long Stay only on 7+ nights, none on Non-refundable' AS check_name, (SELECT count(*) FROM bookings
   WHERE (discount_source = 'Long Stay' AND nights < 7) OR (rate_plan = 'Non-refundable' AND discount_source IS NOT NULL)) AS failures
  UNION ALL
  SELECT 'discount amounts: Long Stay = the Extended Stay rate, Code = the code''s value; the code was valid that day and counts the use' AS check_name, (SELECT (SELECT count(*) FROM bookings b
     LEFT JOIN discount_codes d ON d.code_id = b.discount_code_id
     WHERE (b.discount_source = 'Long Stay' AND b.discount_amount <> round(b.total_amount * (1 - (SELECT rate_multiplier FROM pricing_tiers WHERE tier_name = 'Extended Stay')), 2))
        OR (b.discount_source = 'Code' AND (b.discount_amount <> CASE d.discount_type WHEN 'PERCENTAGE' THEN round(b.total_amount * d.discount_value / 100, 2) ELSE d.discount_value END
                                            OR b.created_at::date NOT BETWEEN d.start_date AND d.end_date)))
   + (SELECT count(*) FROM discount_codes d WHERE d.usage_count < (SELECT count(*) FROM bookings b WHERE b.discount_code_id = d.code_id))) AS failures
  UNION ALL
  SELECT 'a personal discount code is used only by its own guest' AS check_name, (SELECT count(*) FROM bookings b JOIN discount_codes d ON d.code_id = b.discount_code_id
   WHERE d.customer_id IS NOT NULL AND d.customer_id <> b.customer_id) AS failures
  UNION ALL
  SELECT 'an approved Discount Request issued a one-time code to the same guest' AS check_name, (SELECT count(*) FROM customer_requests r JOIN discount_codes d ON d.code_id = r.issued_code_id
   WHERE d.customer_id IS DISTINCT FROM r.customer_id OR d.max_usage <> 1) AS failures
  UNION ALL
  SELECT 'every room type has a Nile photo and all photo paths are under /static/' AS check_name, (SELECT count(*) FROM room_types
   WHERE image_nile NOT LIKE '/static/rooms/%' OR (image_city IS NOT NULL AND image_city NOT LIKE '/static/rooms/%'))
   + (SELECT count(*) FROM hotel_photos WHERE image_path NOT LIKE '/static/hotel/%') AS failures
  UNION ALL
  SELECT 'the settings the API reads are all present' AS check_name, (SELECT count(*) FROM (VALUES ('system_date'), ('free_cancellation_hours'), ('deposit_nights'),
   ('deposit_hold_hours'), ('deposit_hold_hours_last_minute'), ('otp_valid_minutes'), ('otp_max_attempts')) k(key)
   WHERE NOT EXISTS (SELECT 1 FROM app_settings s WHERE s.key = k.key)) AS failures
) AS checks;
