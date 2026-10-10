-- The database itself refuses invalid bookings and payments.
-- Run from database/:   psql -d hotelai -f tests/constraint_checks.sql
-- Every line must say PASS. Everything runs inside a transaction that is rolled back.
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
-- A cancelled booking frees the room: the same insert now succeeds.
UPDATE bookings SET booking_status = 'Cancelled' WHERE booking_id = 'B000006';
INSERT INTO bookings (booking_id, customer_id, room_number, room_type_id, check_in, check_out, adults, children, booking_status, booking_channel, rate_plan, price_per_night) VALUES ('B999995', 'C000375', 804, 'RT003', '2027-06-08', '2027-06-10', 1, 0, 'Confirmed', 'Voice Agent', 'Flexible', 8500);
DO $$ BEGIN RAISE NOTICE 'PASS: after the cancellation the room can be booked again'; END $$;
ROLLBACK;
