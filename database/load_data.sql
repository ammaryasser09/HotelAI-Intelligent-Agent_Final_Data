-- Load the demo data. Run AFTER schema.sql, from the database/ folder:
--     psql -d hotelai -f schema.sql -f load_data.sql
\set ON_ERROR_STOP on
SET client_encoding = 'UTF8';
SET TIME ZONE 'Africa/Cairo';
BEGIN;
\copy app_settings (key, value, description) FROM 'seed/app_settings.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy room_types (room_type_id, room_type_name, description, capacity, base_price, size_sqm) FROM 'seed/room_types.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy rooms (room_number, floor, room_type_id, view, status) FROM 'seed/rooms.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy customers (customer_id, first_name, last_name, first_name_ar, last_name_ar, email, phone, nationality, date_of_birth, created_at) FROM 'seed/customers.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy loyalty_tiers (tier, min_nights_per_year, points_bonus_pct, late_checkout_until, benefits) FROM 'seed/loyalty_tiers.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy loyalty_rules (rule, value, unit, note) FROM 'seed/loyalty_rules.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy loyalty_members (member_id, customer_id, tier, join_date, points_balance, total_stays, status) FROM 'seed/loyalty_members.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy pricing_tiers (pricing_tier_id, tier_name, description, rate_multiplier, status) FROM 'seed/pricing_tiers.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy discount_codes (code_id, discount_code, discount_type, discount_value, usage_count, max_usage, start_date, end_date, status) FROM 'seed/discount_codes.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy services (service_id, service_name, category, description, price, unit, is_available) FROM 'seed/services.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy fees (fee_id, fee_name, amount, unit, rule) FROM 'seed/fees.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy menu_items (item_id, name_en, name_ar, category, price, dietary, night_menu) FROM 'seed/menu_items.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy bookings (booking_id, customer_id, room_number, room_type_id, check_in, check_out, adults, children, booking_status, booking_channel, rate_plan, price_per_night) FROM 'seed/bookings.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy payments (payment_id, booking_id, payment_method, amount_paid, payment_status, refund_amount, transaction_reference) FROM 'seed/payments.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy customer_requests (request_id, customer_id, booking_id, request_type, request_text, request_status, created_at) FROM 'seed/customer_requests.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy complaint_tickets (ticket_id, customer_id, booking_id, complaint_type, priority, description, status, created_at, resolved_at) FROM 'seed/complaint_tickets.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy special_requests (request_id, customer_id, booking_id, request_type, request_text, request_status, created_at, fulfilled_at) FROM 'seed/special_requests.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
\copy customer_feedback (feedback_id, customer_id, booking_id, feedback_category, rating, sentiment, feedback_text, feedback_channel, would_recommend) FROM 'seed/customer_feedback.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
COMMIT;
ANALYZE;
