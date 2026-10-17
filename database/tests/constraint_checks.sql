-- The database itself refuses invalid bookings and payments.
-- Run from database/:   psql -d hotelai -f tests/constraint_checks.sql
-- Every line must say PASS (16 lines). Everything runs inside a transaction that is rolled back.
\set ON_ERROR_STOP on
SET client_min_messages = notice;
BEGIN;
DO $$ BEGIN
    INSERT INTO bookings (booking_id, customer_id, room_number, room_type_id, check_in, check_out, adults, children, booking_status, booking_channel, rate_plan, price_per_night) VALUES ('B999991', 'C000375', 804, 'RT003', '2027-06-08', '2027-06-10', 1, 0, 'Confirmed', 'Voice Agent', 'Flexible', 8500);
    RAISE EXCEPTION 'FAIL: a second booking on the same room and night was accepted';
EXCEPTION WHEN exclusion_violation THEN RAISE NOTICE 'PASS: a second booking on the same room and night refused';
END $$;
DO $$ BEGIN
    INSERT INTO bookings (booking_id, customer_id, room_number, room_type_id, check_in, check_out, adults, children, booking_status, booking_channel, rate_plan, price_per_night) VALUES ('B999992', 'C000375', 401, 'RT002', '2027-09-01', '2027-09-03', 2, 1, 'Confirmed', 'Voice Agent', 'Flexible', 8000);
    RAISE EXCEPTION 'FAIL: 3 guests in a Double (2 adults + 1 child) was accepted';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'PASS: 3 guests in a Double (2 adults + 1 child) refused';
END $$;
DO $$ BEGIN
    INSERT INTO bookings (booking_id, customer_id, room_number, room_type_id, check_in, check_out, adults, children, booking_status, booking_channel, rate_plan, price_per_night) VALUES ('B999993', 'C000375', 1506, 'RT001', '2027-09-01', '2027-09-03', 1, 0, 'Confirmed', 'Voice Agent', 'Flexible', 6000);
    RAISE EXCEPTION 'FAIL: a room booked under another room type was accepted';
EXCEPTION WHEN foreign_key_violation THEN RAISE NOTICE 'PASS: a room booked under another room type refused';
END $$;
DO $$ BEGIN
    INSERT INTO bookings (booking_id, customer_id, room_number, room_type_id, check_in, check_out, adults, children, booking_status, booking_channel, rate_plan, price_per_night) VALUES ('B999994', 'C000375', 401, 'RT002', '2027-09-01', '2027-09-01', 1, 0, 'Confirmed', 'Voice Agent', 'Flexible', 8000);
    RAISE EXCEPTION 'FAIL: check-out on the check-in day was accepted';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'PASS: check-out on the check-in day refused';
END $$;
DO $$ BEGIN
    UPDATE payments SET refund_amount = amount_paid + 1 WHERE booking_id = 'B000006';
    RAISE EXCEPTION 'FAIL: a refund larger than the amount paid was accepted';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'PASS: a refund larger than the amount paid refused';
END $$;
DO $$ BEGIN
    UPDATE bookings SET booking_status = 'Maybe' WHERE booking_id = 'B000006';
    RAISE EXCEPTION 'FAIL: an unknown booking status was accepted';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'PASS: an unknown booking status refused';
END $$;
DO $$ BEGIN
    INSERT INTO discount_codes (code_id, discount_code, discount_type, discount_value, usage_count, max_usage, start_date, end_date, status, customer_id) VALUES ('DC999', 'TESTPERSONAL', 'PERCENTAGE', 10, 0, 2, '2026-09-19', '2026-12-31', 'Active', 'C000375');
    RAISE EXCEPTION 'FAIL: a personal discount code usable twice was accepted';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'PASS: a personal discount code usable more than once refused';
END $$;
DO $$ BEGIN
    UPDATE bookings SET discount_source = 'Code', discount_amount = 500 WHERE booking_id = 'B000006';
    RAISE EXCEPTION 'FAIL: a code discount without a code was accepted';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'PASS: a code discount without a code refused';
END $$;
DO $$ BEGIN
    UPDATE customer_requests SET decision = 'Approved', decided_at = now() WHERE request_id = (SELECT min(request_id) FROM customer_requests WHERE request_type = 'Housekeeping');
    RAISE EXCEPTION 'FAIL: a decision on a Housekeeping request was accepted';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'PASS: a decision on a request that takes none (only Discount and Special Requests do) refused';
END $$;
DO $$ BEGIN
    UPDATE bookings SET discount_source = 'Long Stay', discount_amount = 100 WHERE booking_id = (SELECT min(booking_id) FROM bookings WHERE rate_plan = 'Non-refundable' AND nights >= 7);
    RAISE EXCEPTION 'FAIL: a discount on a Non-refundable booking was accepted';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'PASS: a discount on a Non-refundable booking refused (the rate is already the special price)';
END $$;
DO $$ BEGIN
    UPDATE bookings SET discount_source = 'Long Stay', discount_amount = 100 WHERE booking_id = (SELECT min(booking_id) FROM bookings WHERE rate_plan = 'Flexible' AND nights < 7);
    RAISE EXCEPTION 'FAIL: a Long Stay discount on a short stay was accepted';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'PASS: a Long Stay discount on a stay under 7 nights refused';
END $$;
DO $$ BEGIN
    INSERT INTO customer_requests (customer_id, request_type, request_text, priority) VALUES ('C000375', 'Housekeeping', 'Fire!', 'Critical');
    RAISE EXCEPTION 'FAIL: a Critical ticket that is not an Emergency was accepted';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'PASS: Critical is refused for anything but an Emergency';
END $$;
DO $$ BEGIN
    INSERT INTO customer_requests (request_type, request_text) VALUES ('Room Service', 'A burger to room 410');
    RAISE EXCEPTION 'FAIL: a ticket with no guest and no call was accepted';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'PASS: a ticket with no guest is refused (only a visitor''s Emergency or Staff Callback from a call has none)';
END $$;
DO $$ BEGIN
    UPDATE bookings SET checked_out_at = checked_in_at + interval '1 day' WHERE booking_id = (SELECT min(booking_id) FROM bookings WHERE booking_status = 'Confirmed' AND checked_in_at IS NOT NULL);
    RAISE EXCEPTION 'FAIL: a check-out on a stay that is not Completed was accepted';
EXCEPTION WHEN check_violation THEN RAISE NOTICE 'PASS: a check-out without completing the stay refused';
END $$;
INSERT INTO customer_requests (customer_id, request_type, request_text, request_status) VALUES ('C000375', 'Maintenance', 'The air conditioning is not working', 'Open');
DO $$ BEGIN RAISE NOTICE 'PASS: a Maintenance request is accepted'; END $$;
-- A cancelled booking frees the room: the same insert now succeeds.
UPDATE bookings SET booking_status = 'Cancelled' WHERE booking_id = 'B000006';
INSERT INTO bookings (booking_id, customer_id, room_number, room_type_id, check_in, check_out, adults, children, booking_status, booking_channel, rate_plan, price_per_night) VALUES ('B999995', 'C000375', 804, 'RT003', '2027-06-08', '2027-06-10', 1, 0, 'Confirmed', 'Voice Agent', 'Flexible', 8500);
DO $$ BEGIN RAISE NOTICE 'PASS: after the cancellation the room can be booked again'; END $$;
ROLLBACK;
