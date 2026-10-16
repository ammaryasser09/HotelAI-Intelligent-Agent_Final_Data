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
  SELECT 'amount paid: the total, or the first-night deposit for Flexible stays not completed (0 if nothing collected)' AS check_name, (SELECT count(*) FROM payments p JOIN bookings b USING (booking_id) WHERE
   (p.payment_status IN ('Paid','Refunded','Partially Refunded') AND p.amount_paid <> CASE
      WHEN b.rate_plan = 'Flexible' AND b.booking_status <> 'Completed' THEN b.price_per_night
      ELSE b.total_amount END)
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
  SELECT 'requests, complaints, special requests and feedback filed by the booking holder' AS check_name, (SELECT (SELECT count(*) FROM customer_requests r JOIN bookings b USING (booking_id) WHERE r.customer_id <> b.customer_id)
   + (SELECT count(*) FROM complaint_tickets r JOIN bookings b USING (booking_id) WHERE r.customer_id <> b.customer_id)
   + (SELECT count(*) FROM special_requests r JOIN bookings b USING (booking_id) WHERE r.customer_id <> b.customer_id)
   + (SELECT count(*) FROM customer_feedback r JOIN bookings b USING (booking_id) WHERE r.customer_id <> b.customer_id)) AS failures
  UNION ALL
  SELECT 'nothing dated after system_date' AS check_name, (SELECT (SELECT count(*) FROM customer_requests WHERE created_at::date > hotel_today())
   + (SELECT count(*) FROM complaint_tickets WHERE created_at::date > hotel_today() OR resolved_at::date > hotel_today())
   + (SELECT count(*) FROM special_requests WHERE created_at::date > hotel_today() OR fulfilled_at::date > hotel_today())
   + (SELECT count(*) FROM customers WHERE created_at::date > hotel_today())) AS failures
  UNION ALL
  SELECT 'guests registered before their first stay' AS check_name, (SELECT count(*) FROM customers c JOIN (SELECT customer_id, min(check_in) AS first_in FROM bookings GROUP BY 1) f
   USING (customer_id) WHERE c.created_at::date > f.first_in) AS failures
  UNION ALL
  SELECT 'booking holders are 18+ at check-in' AS check_name, (SELECT count(*) FROM bookings b JOIN customers c USING (customer_id) WHERE b.check_in < c.date_of_birth + interval '18 years') AS failures
  UNION ALL
  SELECT 'room status snapshot agrees with the bookings on system_date' AS check_name, (SELECT count(*) FROM rooms r WHERE (r.status = 'Occupied') <> EXISTS (SELECT 1 FROM bookings b
   WHERE b.room_number = r.room_number AND b.booking_status IN ('Confirmed','Completed') AND b.check_in <= hotel_today() AND hotel_today() < b.check_out)) AS failures
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
  SELECT 'emergencies are Critical and staff callbacks Urgent' AS check_name, (SELECT count(*) FROM customer_requests WHERE
   (request_type = 'Emergency') <> (priority = 'Critical') OR (request_type = 'Staff Callback') <> (priority = 'Urgent')) AS failures
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
) AS checks;
