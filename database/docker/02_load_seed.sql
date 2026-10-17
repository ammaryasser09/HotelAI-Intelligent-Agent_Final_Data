-- Runs once inside the postgres container (docker-entrypoint-initdb.d), after 01_schema.sql.
SET client_encoding = 'UTF8';
SET TIME ZONE 'Africa/Cairo';
COPY app_settings (key, value, description) FROM '/seed/app_settings.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
COPY room_types (room_type_id, room_type_name, description, capacity, base_price, size_sqm, image_nile, image_city) FROM '/seed/room_types.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
COPY rooms (room_number, floor, room_type_id, view, status) FROM '/seed/rooms.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
COPY customers (customer_id, first_name, last_name, first_name_ar, last_name_ar, email, phone, nationality, date_of_birth, created_at) FROM '/seed/customers.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
COPY loyalty_tiers (tier, min_nights_per_year, points_bonus_pct, late_checkout_until, benefits) FROM '/seed/loyalty_tiers.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
COPY loyalty_rules (rule, value, unit, note) FROM '/seed/loyalty_rules.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
COPY loyalty_members (member_id, customer_id, tier, join_date, points_balance, total_stays, status) FROM '/seed/loyalty_members.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
COPY pricing_tiers (pricing_tier_id, tier_name, description, rate_multiplier, status) FROM '/seed/pricing_tiers.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
COPY discount_codes (code_id, discount_code, discount_type, discount_value, usage_count, max_usage, start_date, end_date, status, customer_id) FROM '/seed/discount_codes.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
COPY services (service_id, service_name, category, description, price, unit, is_available) FROM '/seed/services.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
COPY hotel_photos (photo_key, title_en, title_ar, image_path, service_id) FROM '/seed/hotel_photos.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
COPY fees (fee_id, fee_name, amount, unit, rule) FROM '/seed/fees.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
COPY menu_items (item_id, name_en, name_ar, category, price, dietary, night_menu) FROM '/seed/menu_items.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
COPY bookings (booking_id, customer_id, room_number, room_type_id, check_in, check_out, adults, children, booking_status, booking_channel, rate_plan, price_per_night, discount_source, discount_code_id, discount_amount, created_at, checked_in_at, checked_out_at) FROM '/seed/bookings.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
COPY payments (payment_id, booking_id, payment_method, amount_paid, payment_status, refund_amount, transaction_reference, payment_due_at) FROM '/seed/payments.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
COPY user_accounts (account_id, role, customer_id, full_name, email, password_hash, email_verified, is_active, created_at, last_login_at) FROM '/seed/user_accounts.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
COPY booking_links (account_id, booking_id, linked_at) FROM '/seed/booking_links.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
DO $$ BEGIN PERFORM setval(pg_get_serial_sequence('user_accounts', 'account_id'), (SELECT max(account_id) FROM user_accounts)); END $$;
COPY calls (call_id, channel, language, account_id, customer_id, booking_id, status, escalation_reason, assigned_staff_id, summary, started_at, ended_at) FROM '/seed/calls.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
COPY call_messages (call_id, turn_no, role, content, latency_ms, created_at) FROM '/seed/call_messages.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
COPY call_actions (call_id, tool_name, arguments, result, success, booking_id, created_at) FROM '/seed/call_actions.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
COPY customer_requests (request_id, customer_id, booking_id, call_id, request_type, category, priority, request_text, request_status, handled_by, decision, decided_by, decided_at, issued_code_id, created_at, resolved_at) FROM '/seed/customer_requests.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
COPY customer_feedback (feedback_id, customer_id, booking_id, feedback_category, rating, sentiment, feedback_text, feedback_channel, would_recommend) FROM '/seed/customer_feedback.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
-- Reference sequences continue after the highest id in the data (B020002 -> the next booking is B020003).
DO $$ BEGIN
    PERFORM setval('customers_id_seq', (SELECT max(substr(customer_id, 2)::int) FROM customers));
    PERFORM setval('loyalty_members_id_seq', (SELECT max(substr(member_id, 3)::int) FROM loyalty_members));
    PERFORM setval('bookings_id_seq', (SELECT max(substr(booking_id, 2)::int) FROM bookings));
    PERFORM setval('payments_id_seq', (SELECT max(substr(payment_id, 2)::int) FROM payments));
    PERFORM setval('customer_requests_id_seq', (SELECT max(substr(request_id, 4)::int) FROM customer_requests));
    PERFORM setval('customer_feedback_id_seq', (SELECT max(substr(feedback_id, 3)::int) FROM customer_feedback));
END $$;
ANALYZE;
