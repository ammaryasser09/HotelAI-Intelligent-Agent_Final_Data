-- Nile Pearl Hotel (HotelAI) - PostgreSQL schema
-- Running this file DROPS and recreates every table. Load the data afterwards with load_data.sql.
-- Column meanings: DATA_DICTIONARY.md (also stored below as COMMENTs). Change both together.
-- Requires PostgreSQL 13+ (gen_random_uuid) and the btree_gist extension (bundled with PostgreSQL).

SET client_encoding = 'UTF8';
SET client_min_messages = warning;
CREATE EXTENSION IF NOT EXISTS btree_gist;
DO $$ BEGIN EXECUTE format('ALTER DATABASE %I SET timezone TO %L', current_database(), 'Africa/Cairo'); END $$;
SET TIME ZONE 'Africa/Cairo';

DROP VIEW IF EXISTS v_call_overview, v_booking_details CASCADE;
DROP TABLE IF EXISTS call_actions, call_messages, calls, booking_links, user_accounts, staff_users, customer_feedback, special_requests, complaint_tickets, customer_requests, payments, bookings, menu_items, fees, services, discount_codes, pricing_tiers, loyalty_members, loyalty_rules, loyalty_tiers, customers, rooms, room_types, app_settings CASCADE;
DROP FUNCTION IF EXISTS hotel_today(), free_rooms(text, date, date), check_booking_capacity() CASCADE;
DROP SEQUENCE IF EXISTS customers_id_seq, loyalty_members_id_seq, bookings_id_seq, payments_id_seq, customer_requests_id_seq, complaint_tickets_id_seq, special_requests_id_seq, customer_feedback_id_seq;

-- ID sequences: new rows get the next reference in the same format as the demo data
CREATE SEQUENCE customers_id_seq START WITH 10001;
CREATE SEQUENCE loyalty_members_id_seq START WITH 101;
CREATE SEQUENCE bookings_id_seq START WITH 20001;
CREATE SEQUENCE payments_id_seq START WITH 20001;
CREATE SEQUENCE customer_requests_id_seq START WITH 15001;
CREATE SEQUENCE complaint_tickets_id_seq START WITH 76;
CREATE SEQUENCE special_requests_id_seq START WITH 126;
CREATE SEQUENCE customer_feedback_id_seq START WITH 5001;

-- Hotel settings: app_settings
CREATE TABLE app_settings (
    key                      VARCHAR(40)    PRIMARY KEY,
    value                    TEXT           NOT NULL,
    description              TEXT
);

-- Rooms: room_types
CREATE TABLE room_types (
    room_type_id             VARCHAR(5)     PRIMARY KEY,
    room_type_name           VARCHAR(20)    NOT NULL UNIQUE,
    description              TEXT           NOT NULL,
    capacity                 SMALLINT       NOT NULL CHECK (capacity BETWEEN 1 AND 4),
    base_price               NUMERIC(10,2)  NOT NULL CHECK (base_price > 0),
    size_sqm                 SMALLINT       NOT NULL CHECK (size_sqm > 0),
    image_nile               VARCHAR(80)    NOT NULL,
    image_city               VARCHAR(80)
);

-- Rooms: rooms
CREATE TABLE rooms (
    room_number              SMALLINT       PRIMARY KEY,
    floor                    SMALLINT       NOT NULL CHECK (floor BETWEEN 2 AND 16),
    room_type_id             VARCHAR(5)     NOT NULL REFERENCES room_types,
    view                     VARCHAR(4)     NOT NULL CHECK (view IN ('Nile', 'City')),
    status                   VARCHAR(11)    NOT NULL CHECK (status IN ('Available', 'Occupied', 'Maintenance')),
    UNIQUE (room_number, room_type_id)
);

-- Guests: customers
CREATE TABLE customers (
    customer_id              VARCHAR(7)     PRIMARY KEY DEFAULT 'C' || lpad(nextval('customers_id_seq')::text, 6, '0'),
    first_name               VARCHAR(40)    NOT NULL,
    last_name                VARCHAR(40)    NOT NULL,
    first_name_ar            VARCHAR(40),
    last_name_ar             VARCHAR(40),
    email                    VARCHAR(120)   NOT NULL UNIQUE,
    phone                    VARCHAR(20)    NOT NULL UNIQUE,
    nationality              VARCHAR(30),
    date_of_birth            DATE,
    created_at               TIMESTAMPTZ    NOT NULL DEFAULT now()
);

-- Loyalty: loyalty_tiers
CREATE TABLE loyalty_tiers (
    tier                     VARCHAR(10)    PRIMARY KEY,
    min_nights_per_year      SMALLINT       NOT NULL CHECK (min_nights_per_year >= 0),
    points_bonus_pct         SMALLINT       NOT NULL CHECK (points_bonus_pct >= 0),
    late_checkout_until      TIME,
    benefits                 TEXT           NOT NULL
);

-- Loyalty: loyalty_rules
CREATE TABLE loyalty_rules (
    rule                     VARCHAR(30)    PRIMARY KEY,
    value                    NUMERIC(10,2)  NOT NULL,
    unit                     VARCHAR(20)    NOT NULL,
    note                     TEXT           NOT NULL
);

-- Loyalty: loyalty_members
CREATE TABLE loyalty_members (
    member_id                VARCHAR(7)     PRIMARY KEY DEFAULT 'LM' || lpad(nextval('loyalty_members_id_seq')::text, 5, '0'),
    customer_id              VARCHAR(7)     NOT NULL UNIQUE REFERENCES customers,
    tier                     VARCHAR(10)    NOT NULL REFERENCES loyalty_tiers,
    join_date                DATE           NOT NULL,
    points_balance           INTEGER        NOT NULL CHECK (points_balance >= 0),
    total_stays              INTEGER        NOT NULL CHECK (total_stays >= 0),
    status                   VARCHAR(10)    NOT NULL CHECK (status IN ('Active', 'Inactive'))
);

-- Pricing: pricing_tiers
CREATE TABLE pricing_tiers (
    pricing_tier_id          VARCHAR(5)     PRIMARY KEY,
    tier_name                VARCHAR(30)    NOT NULL UNIQUE,
    description              TEXT           NOT NULL,
    rate_multiplier          NUMERIC(4,2)   NOT NULL CHECK (rate_multiplier > 0),
    status                   VARCHAR(10)    NOT NULL CHECK (status IN ('Active', 'Inactive'))
);

-- Pricing: discount_codes
CREATE TABLE discount_codes (
    code_id                  VARCHAR(5)     PRIMARY KEY,
    discount_code            VARCHAR(20)    NOT NULL UNIQUE,
    discount_type            VARCHAR(12)    NOT NULL CHECK (discount_type IN ('PERCENTAGE', 'FIXED_AMOUNT')),
    discount_value           NUMERIC(10,2)  NOT NULL CHECK (discount_value > 0),
    usage_count              INTEGER        NOT NULL CHECK (usage_count >= 0),
    max_usage                INTEGER        CHECK (max_usage > 0),
    start_date               DATE           NOT NULL,
    end_date                 DATE           NOT NULL,
    status                   VARCHAR(10)    NOT NULL CHECK (status IN ('Active', 'Scheduled', 'Exhausted', 'Expired')),
    CHECK (end_date >= start_date),
    CHECK (max_usage IS NULL OR usage_count <= max_usage),
    CHECK (discount_type <> 'PERCENTAGE' OR discount_value <= 100)
);

-- Services: services
CREATE TABLE services (
    service_id               VARCHAR(4)     PRIMARY KEY,
    service_name             VARCHAR(40)    NOT NULL UNIQUE,
    category                 VARCHAR(30)    NOT NULL,
    description              TEXT           NOT NULL,
    price                    NUMERIC(10,2)  NOT NULL CHECK (price >= 0),
    unit                     VARCHAR(20)    NOT NULL,
    is_available             BOOLEAN        NOT NULL DEFAULT true
);

-- Services: fees
CREATE TABLE fees (
    fee_id                   VARCHAR(4)     PRIMARY KEY,
    fee_name                 VARCHAR(60)    NOT NULL UNIQUE,
    amount                   NUMERIC(10,2)  NOT NULL,
    unit                     VARCHAR(30)    NOT NULL,
    rule                     TEXT           NOT NULL
);

-- Services: menu_items
CREATE TABLE menu_items (
    item_id                  VARCHAR(3)     PRIMARY KEY,
    name_en                  VARCHAR(60)    NOT NULL UNIQUE,
    name_ar                  VARCHAR(60)    NOT NULL UNIQUE,
    category                 VARCHAR(20)    NOT NULL,
    price                    NUMERIC(10,2)  NOT NULL CHECK (price > 0),
    dietary                  VARCHAR(20),
    night_menu               BOOLEAN        NOT NULL
);

-- Reservations: bookings
CREATE TABLE bookings (
    booking_id               VARCHAR(7)     PRIMARY KEY DEFAULT 'B' || lpad(nextval('bookings_id_seq')::text, 6, '0'),
    customer_id              VARCHAR(7)     NOT NULL REFERENCES customers,
    room_number              SMALLINT       NOT NULL,
    room_type_id             VARCHAR(5)     NOT NULL,
    check_in                 DATE           NOT NULL,
    check_out                DATE           NOT NULL,
    nights                   INTEGER        GENERATED ALWAYS AS (check_out - check_in) STORED,
    adults                   SMALLINT       NOT NULL CHECK (adults >= 1),
    children                 SMALLINT       NOT NULL DEFAULT 0 CHECK (children >= 0),
    booking_status           VARCHAR(10)    NOT NULL CHECK (booking_status IN ('Pending', 'Confirmed', 'Completed', 'Cancelled', 'No-show')),
    booking_channel          VARCHAR(20)    NOT NULL CHECK (booking_channel IN ('Website', 'Booking Platform', 'Mobile App', 'Phone', 'Travel Agent', 'Voice Agent')),
    rate_plan                VARCHAR(14)    NOT NULL CHECK (rate_plan IN ('Flexible', 'Non-refundable')),
    price_per_night          NUMERIC(10,2)  NOT NULL CHECK (price_per_night > 0),
    total_amount             NUMERIC(12,2)  GENERATED ALWAYS AS (price_per_night * (check_out - check_in)) STORED,
    created_at               TIMESTAMPTZ,
    cancelled_at             TIMESTAMPTZ,
    checked_in_at            TIMESTAMPTZ,
    checked_out_at           TIMESTAMPTZ,
    CHECK (check_out > check_in),
    FOREIGN KEY (room_number, room_type_id) REFERENCES rooms (room_number, room_type_id),
    CONSTRAINT no_double_booking EXCLUDE USING gist (room_number WITH =, daterange(check_in, check_out, '[)') WITH &&) WHERE (booking_status IN ('Pending', 'Confirmed', 'Completed'))
);

-- Reservations: payments
CREATE TABLE payments (
    payment_id               VARCHAR(7)     PRIMARY KEY DEFAULT 'P' || lpad(nextval('payments_id_seq')::text, 6, '0'),
    booking_id               VARCHAR(7)     NOT NULL UNIQUE REFERENCES bookings ON DELETE CASCADE,
    payment_method           VARCHAR(20)    NOT NULL CHECK (payment_method IN ('Credit Card', 'Debit Card', 'Cash', 'Digital Wallet', 'Bank Transfer')),
    amount_paid              NUMERIC(12,2)  NOT NULL DEFAULT 0 CHECK (amount_paid >= 0),
    payment_status           VARCHAR(20)    NOT NULL CHECK (payment_status IN ('Pending', 'Paid', 'Failed', 'Expired', 'Refunded', 'Partially Refunded')),
    refund_amount            NUMERIC(12,2)  NOT NULL DEFAULT 0 CHECK (refund_amount >= 0),
    transaction_reference    UUID           NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    payment_due_at           TIMESTAMPTZ,
    created_at               TIMESTAMPTZ,
    CHECK (refund_amount <= amount_paid)
);

-- Guest service: customer_requests
CREATE TABLE customer_requests (
    request_id               VARCHAR(9)     PRIMARY KEY DEFAULT 'REQ' || lpad(nextval('customer_requests_id_seq')::text, 6, '0'),
    customer_id              VARCHAR(7)     NOT NULL REFERENCES customers,
    booking_id               VARCHAR(7)     REFERENCES bookings ON DELETE SET NULL,
    request_type             VARCHAR(25)    NOT NULL CHECK (request_type IN ('Room Service', 'Booking Inquiry', 'Housekeeping', 'Late Checkout', 'Modification Request', 'Airport Transfer', 'General Inquiry', 'Cancellation Request', 'Complaint', 'Extra Bed', 'Early Check-in', 'Payment Inquiry', 'Discount Request', 'Staff Callback', 'Emergency')),
    priority                 VARCHAR(8)     NOT NULL DEFAULT 'Normal' CHECK (priority IN ('Normal', 'Urgent', 'Critical')),
    request_text             TEXT           NOT NULL,
    request_status           VARCHAR(12)    NOT NULL CHECK (request_status IN ('Open', 'In Progress', 'Resolved', 'Closed')),
    created_at               TIMESTAMPTZ    NOT NULL DEFAULT now()
);

-- Guest service: complaint_tickets
CREATE TABLE complaint_tickets (
    ticket_id                VARCHAR(8)     PRIMARY KEY DEFAULT 'CMP' || lpad(nextval('complaint_tickets_id_seq')::text, 5, '0'),
    customer_id              VARCHAR(7)     NOT NULL REFERENCES customers,
    booking_id               VARCHAR(7)     REFERENCES bookings ON DELETE SET NULL,
    complaint_type           VARCHAR(20)    NOT NULL CHECK (complaint_type IN ('Room Issue', 'Service Issue', 'Facility Issue', 'Billing Issue', 'Booking Issue')),
    priority                 VARCHAR(10)    NOT NULL CHECK (priority IN ('Low', 'Medium', 'High', 'Critical')),
    description              TEXT           NOT NULL,
    status                   VARCHAR(12)    NOT NULL CHECK (status IN ('Open', 'In Progress', 'Resolved', 'Closed')),
    created_at               TIMESTAMPTZ    NOT NULL DEFAULT now(),
    resolved_at              TIMESTAMPTZ,
    CHECK (resolved_at IS NULL OR resolved_at >= created_at),
    CHECK ((status IN ('Resolved', 'Closed')) = (resolved_at IS NOT NULL))
);

-- Guest service: special_requests
CREATE TABLE special_requests (
    request_id               VARCHAR(7)     PRIMARY KEY DEFAULT 'SR' || lpad(nextval('special_requests_id_seq')::text, 5, '0'),
    customer_id              VARCHAR(7)     NOT NULL REFERENCES customers,
    booking_id               VARCHAR(7)     NOT NULL REFERENCES bookings ON DELETE CASCADE,
    request_type             VARCHAR(25)    NOT NULL CHECK (request_type IN ('Checkout Extension', 'Service Request', 'Celebration Arrangement', 'Dietary Requirement', 'Transportation', 'Accessibility Request', 'Room Preference')),
    request_text             TEXT           NOT NULL,
    request_status           VARCHAR(10)    NOT NULL CHECK (request_status IN ('Pending', 'Approved', 'Denied', 'Cancelled', 'Fulfilled')),
    created_at               TIMESTAMPTZ    NOT NULL DEFAULT now(),
    fulfilled_at             TIMESTAMPTZ,
    CHECK ((request_status = 'Fulfilled') = (fulfilled_at IS NOT NULL)),
    CHECK (fulfilled_at IS NULL OR fulfilled_at >= created_at)
);

-- Guest service: customer_feedback
CREATE TABLE customer_feedback (
    feedback_id              VARCHAR(8)     PRIMARY KEY DEFAULT 'FB' || lpad(nextval('customer_feedback_id_seq')::text, 6, '0'),
    customer_id              VARCHAR(7)     NOT NULL REFERENCES customers,
    booking_id               VARCHAR(7)     NOT NULL UNIQUE REFERENCES bookings ON DELETE CASCADE,
    feedback_category        VARCHAR(20)    NOT NULL CHECK (feedback_category IN ('Room', 'Booking', 'Staff', 'Facilities', 'Service', 'Overall Experience', 'Food', 'Payment', 'Location', 'Cleanliness')),
    rating                   SMALLINT       NOT NULL CHECK (rating BETWEEN 1 AND 5),
    sentiment                VARCHAR(8)     NOT NULL CHECK (sentiment IN ('Positive', 'Neutral', 'Negative')),
    feedback_text            TEXT           NOT NULL,
    feedback_channel         VARCHAR(12)    NOT NULL CHECK (feedback_channel IN ('Mobile App', 'Website', 'In-Hotel', 'Email', 'Survey', 'Voice Agent')),
    would_recommend          VARCHAR(5)     NOT NULL CHECK (would_recommend IN ('Yes', 'Maybe', 'No')),
    CHECK ((rating >= 4 AND sentiment = 'Positive') OR (rating = 3 AND sentiment = 'Neutral') OR (rating <= 2 AND sentiment = 'Negative'))
);

-- Accounts: user_accounts (one login page for guests, staff and admins)
CREATE TABLE user_accounts (
    account_id               SERIAL         PRIMARY KEY,
    role                     VARCHAR(5)     NOT NULL CHECK (role IN ('Guest', 'Staff', 'Admin')),
    customer_id              VARCHAR(7)     UNIQUE REFERENCES customers,
    full_name                VARCHAR(80)    NOT NULL,
    email                    VARCHAR(120)   NOT NULL UNIQUE,
    password_hash            TEXT           NOT NULL,
    email_verified           BOOLEAN        NOT NULL DEFAULT false,
    is_active                BOOLEAN        NOT NULL DEFAULT true,
    created_at               TIMESTAMPTZ    NOT NULL DEFAULT now(),
    last_login_at            TIMESTAMPTZ,
    CHECK ((role = 'Guest') = (customer_id IS NOT NULL))
);

-- Accounts: booking_links (a booking made elsewhere, added to an account with reference + last name or phone digits)
CREATE TABLE booking_links (
    account_id               INTEGER        NOT NULL REFERENCES user_accounts ON DELETE CASCADE,
    booking_id               VARCHAR(7)     NOT NULL REFERENCES bookings ON DELETE CASCADE,
    linked_at                TIMESTAMPTZ    NOT NULL DEFAULT now(),
    PRIMARY KEY (account_id, booking_id)
);

-- Dashboard: calls
CREATE TABLE calls (
    call_id                  UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    channel                  VARCHAR(5)     NOT NULL DEFAULT 'voice' CHECK (channel IN ('voice', 'text')),
    language                 VARCHAR(16)    CHECK (language IN ('Arabic-Egyptian', 'Arabic', 'English', 'French', 'Russian')),
    customer_id              VARCHAR(7)     REFERENCES customers,
    booking_id               VARCHAR(7)     REFERENCES bookings,
    identity_verified        BOOLEAN        NOT NULL DEFAULT false,
    status                   VARCHAR(10)    NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'escalated', 'abandoned')),
    escalation_reason        TEXT,
    assigned_staff_id        INTEGER        REFERENCES user_accounts,
    summary                  TEXT,
    started_at               TIMESTAMPTZ    NOT NULL DEFAULT now(),
    ended_at                 TIMESTAMPTZ,
    CHECK (ended_at IS NULL OR ended_at >= started_at),
    CHECK (status <> 'escalated' OR escalation_reason IS NOT NULL)
);

-- Dashboard: call_messages
CREATE TABLE call_messages (
    message_id               BIGSERIAL      PRIMARY KEY,
    call_id                  UUID           NOT NULL REFERENCES calls ON DELETE CASCADE,
    turn_no                  INTEGER        NOT NULL CHECK (turn_no >= 1),
    role                     VARCHAR(6)     NOT NULL CHECK (role IN ('guest', 'agent', 'staff', 'system')),
    content                  TEXT           NOT NULL,
    latency_ms               INTEGER        CHECK (latency_ms >= 0),
    created_at               TIMESTAMPTZ    NOT NULL DEFAULT now(),
    UNIQUE (call_id, turn_no)
);

-- Dashboard: call_actions
CREATE TABLE call_actions (
    action_id                BIGSERIAL      PRIMARY KEY,
    call_id                  UUID           NOT NULL REFERENCES calls ON DELETE CASCADE,
    tool_name                VARCHAR(40)    NOT NULL,
    arguments                JSONB          NOT NULL DEFAULT '{}'::jsonb,
    result                   JSONB,
    success                  BOOLEAN        NOT NULL,
    booking_id               VARCHAR(7)     REFERENCES bookings,
    created_at               TIMESTAMPTZ    NOT NULL DEFAULT now()
);
ALTER SEQUENCE customers_id_seq OWNED BY customers.customer_id;
ALTER SEQUENCE loyalty_members_id_seq OWNED BY loyalty_members.member_id;
ALTER SEQUENCE bookings_id_seq OWNED BY bookings.booking_id;
ALTER SEQUENCE payments_id_seq OWNED BY payments.payment_id;
ALTER SEQUENCE customer_requests_id_seq OWNED BY customer_requests.request_id;
ALTER SEQUENCE complaint_tickets_id_seq OWNED BY complaint_tickets.ticket_id;
ALTER SEQUENCE special_requests_id_seq OWNED BY special_requests.request_id;
ALTER SEQUENCE customer_feedback_id_seq OWNED BY customer_feedback.feedback_id;

-- Indexes
CREATE INDEX idx_bookings_customer ON bookings (customer_id);
CREATE INDEX idx_bookings_check_in ON bookings (check_in);
CREATE INDEX idx_bookings_type_dates ON bookings (room_type_id, check_in, check_out) WHERE booking_status IN ('Pending', 'Confirmed', 'Completed');
CREATE INDEX idx_customers_last_name ON customers (lower(last_name));
CREATE INDEX idx_customers_last_name_ar ON customers (last_name_ar);
CREATE INDEX idx_customers_phone_last4 ON customers (right(phone, 4));
CREATE INDEX idx_requests_customer ON customer_requests (customer_id);
CREATE INDEX idx_requests_booking ON customer_requests (booking_id);
CREATE INDEX idx_complaints_customer ON complaint_tickets (customer_id);
CREATE INDEX idx_complaints_status ON complaint_tickets (status);
CREATE INDEX idx_special_booking ON special_requests (booking_id);
CREATE INDEX idx_feedback_customer ON customer_feedback (customer_id);
CREATE INDEX idx_calls_started ON calls (started_at DESC);
CREATE INDEX idx_calls_status ON calls (status);
CREATE INDEX idx_actions_call ON call_actions (call_id);

-- Functions and rules
-- "Today" of the dataset (app_settings.system_date), so SQL and the API agree on one date.
CREATE FUNCTION hotel_today() RETURNS date LANGUAGE sql STABLE AS $$
    SELECT value::date FROM app_settings WHERE key = 'system_date'
$$;

-- Free rooms of a type for the nights [p_check_in, p_check_out). Accepts RT00x or the type name.
-- A room is busy when a Pending (held until its payment is due), Confirmed or Completed booking overlaps;
-- Cancelled and No-show never block.
-- Back-to-back stays are allowed: a booking that checks out on p_check_in does not overlap.
CREATE FUNCTION free_rooms(p_room_type text, p_check_in date, p_check_out date)
RETURNS TABLE (room_number smallint, floor smallint, view varchar) LANGUAGE sql STABLE AS $$
    SELECT r.room_number, r.floor, r.view
    FROM rooms r JOIN room_types t ON t.room_type_id = r.room_type_id
    WHERE (t.room_type_id = upper(p_room_type) OR lower(t.room_type_name) = lower(p_room_type))
      AND r.status <> 'Maintenance'
      AND NOT EXISTS (SELECT 1 FROM bookings b
                      WHERE b.room_number = r.room_number
                        AND b.booking_status IN ('Pending', 'Confirmed', 'Completed')
                        AND b.check_in < p_check_out AND p_check_in < b.check_out)
    ORDER BY (r.view = 'Nile') DESC, r.room_number
$$;

-- Capacity rule: adults + children must fit the room type (an extra bed does not raise capacity).
CREATE FUNCTION check_booking_capacity() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE cap smallint;
BEGIN
    SELECT capacity INTO cap FROM room_types WHERE room_type_id = NEW.room_type_id;
    IF NEW.adults + NEW.children > cap THEN
        RAISE EXCEPTION 'capacity exceeded: % guests for room type % (capacity %)',
            NEW.adults + NEW.children, NEW.room_type_id, cap USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER trg_booking_capacity BEFORE INSERT OR UPDATE OF adults, children, room_type_id ON bookings
    FOR EACH ROW EXECUTE FUNCTION check_booking_capacity();

-- Views
-- Everything the agent may tell a verified caller about a booking, in one row.
CREATE VIEW v_booking_details AS
SELECT b.booking_id, b.booking_status, b.rate_plan, b.booking_channel,
       b.check_in, b.check_out, b.nights, b.adults, b.children,
       b.price_per_night, b.total_amount,
       c.customer_id, c.first_name, c.last_name, c.first_name_ar, c.last_name_ar,
       right(c.phone, 4) AS phone_last4, c.email,
       t.room_type_name, b.room_number, r.floor, r.view,
       p.payment_method, p.payment_status, p.amount_paid, p.refund_amount, p.payment_due_at
FROM bookings b
JOIN customers c  ON c.customer_id = b.customer_id
JOIN room_types t ON t.room_type_id = b.room_type_id
JOIN rooms r      ON r.room_number = b.room_number
LEFT JOIN payments p ON p.booking_id = b.booking_id;

-- Dashboard list of calls.
CREATE VIEW v_call_overview AS
SELECT c.call_id, c.started_at, c.ended_at, c.channel, c.language, c.status, c.escalation_reason,
       c.identity_verified, c.booking_id, c.customer_id,
       cu.first_name || ' ' || cu.last_name AS guest_name,
       s.full_name AS assigned_to,
       (SELECT count(*) FROM call_messages m WHERE m.call_id = c.call_id) AS turns,
       (SELECT count(*) FROM call_actions a WHERE a.call_id = c.call_id) AS actions,
       (SELECT round(avg(m.latency_ms)) FROM call_messages m WHERE m.call_id = c.call_id AND m.role = 'agent') AS avg_latency_ms,
       extract(epoch FROM (c.ended_at - c.started_at))::int AS duration_seconds
FROM calls c
LEFT JOIN customers cu ON cu.customer_id = c.customer_id
LEFT JOIN user_accounts s ON s.account_id = c.assigned_staff_id;

-- The bookings a logged-in guest can see: those under the account's customer, plus bookings linked to it.
CREATE VIEW v_account_bookings AS
SELECT a.account_id, b.booking_id, 'own'::text AS access
FROM user_accounts a JOIN bookings b ON b.customer_id = a.customer_id
UNION ALL
SELECT l.account_id, l.booking_id, 'linked' FROM booking_links l;

-- Comments (visible in pgAdmin and \d+)
COMMENT ON TABLE app_settings IS 'Hotel-wide settings. system_date is the frozen "today" of the dataset; the API must use it instead of the machine clock while the demo data is in use.';
COMMENT ON COLUMN app_settings.key IS 'Setting name';
COMMENT ON COLUMN app_settings.value IS 'Setting value (text; cast in the application)';
COMMENT ON COLUMN app_settings.description IS 'What the setting means';
COMMENT ON TABLE room_types IS 'The six room categories, their capacity and standard nightly rate (EGP, taxes included, room only).';
COMMENT ON COLUMN room_types.room_type_id IS 'RT001-RT006';
COMMENT ON COLUMN room_types.room_type_name IS 'Single, Double, Twin, Deluxe, Family, Suite';
COMMENT ON COLUMN room_types.description IS 'Short description';
COMMENT ON COLUMN room_types.capacity IS 'Maximum guests, adults and children together';
COMMENT ON COLUMN room_types.base_price IS 'Standard Flexible rate per night, EGP';
COMMENT ON COLUMN room_types.size_sqm IS 'Room size in square metres';
COMMENT ON COLUMN room_types.image_nile IS 'Photo of the room type with a Nile view (path under static/)';
COMMENT ON COLUMN room_types.image_city IS 'Photo with a city view; NULL for the Suite (every Suite faces the Nile)';
COMMENT ON TABLE rooms IS '150 rooms on floors 2-16. room_number = floor x 100 + n; rooms 1-5 of a floor and every Suite face the Nile.';
COMMENT ON COLUMN rooms.room_number IS 'Room number as told to the guest, e.g. 1307';
COMMENT ON COLUMN rooms.floor IS 'Floor';
COMMENT ON COLUMN rooms.room_type_id IS 'Room type';
COMMENT ON COLUMN rooms.view IS 'Nile or City';
COMMENT ON COLUMN rooms.status IS 'Snapshot on system_date. Availability for any dates is computed from bookings, not from this column; a room in Maintenance is never offered.';
COMMENT ON TABLE customers IS 'Guests. Arab guests also carry the Arabic spelling of their name, so a caller who gives an Arabic name is found.';
COMMENT ON COLUMN customers.customer_id IS 'C + 6 digits';
COMMENT ON COLUMN customers.first_name IS 'First name (Latin)';
COMMENT ON COLUMN customers.last_name IS 'Last name (Latin)';
COMMENT ON COLUMN customers.first_name_ar IS 'First name in Arabic, Arab guests only';
COMMENT ON COLUMN customers.last_name_ar IS 'Last name in Arabic, Arab guests only';
COMMENT ON COLUMN customers.email IS 'Email';
COMMENT ON COLUMN customers.phone IS 'Phone in international format; its last 4 digits are used for the identity check';
COMMENT ON COLUMN customers.nationality IS 'Nationality';
COMMENT ON COLUMN customers.date_of_birth IS 'Date of birth';
COMMENT ON COLUMN customers.created_at IS 'Account creation time (Cairo time)';
COMMENT ON TABLE loyalty_tiers IS 'Nile Pearl Rewards tiers: nights needed per calendar year, points bonus and free late check-out.';
COMMENT ON COLUMN loyalty_tiers.tier IS 'Standard, Silver, Gold, Platinum';
COMMENT ON COLUMN loyalty_tiers.min_nights_per_year IS 'Nights in a calendar year to reach the tier';
COMMENT ON COLUMN loyalty_tiers.points_bonus_pct IS 'Extra points on top of the base earn rate, %';
COMMENT ON COLUMN loyalty_tiers.late_checkout_until IS 'Free late check-out until this time (NULL = none)';
COMMENT ON COLUMN loyalty_tiers.benefits IS 'Benefits as told to the guest';
COMMENT ON TABLE loyalty_rules IS 'Programme rules as numbers: earn rate, redemption, expiry, referral bonus, member discount.';
COMMENT ON COLUMN loyalty_rules.rule IS 'Rule name';
COMMENT ON COLUMN loyalty_rules.value IS 'Rule value';
COMMENT ON COLUMN loyalty_rules.unit IS 'Unit of the value';
COMMENT ON COLUMN loyalty_rules.note IS 'Meaning';
COMMENT ON TABLE loyalty_members IS 'Programme members: one membership per guest.';
COMMENT ON COLUMN loyalty_members.member_id IS 'LM + 5 digits';
COMMENT ON COLUMN loyalty_members.customer_id IS 'The member';
COMMENT ON COLUMN loyalty_members.tier IS 'Current tier';
COMMENT ON COLUMN loyalty_members.join_date IS 'Joining date';
COMMENT ON COLUMN loyalty_members.points_balance IS 'Points available';
COMMENT ON COLUMN loyalty_members.total_stays IS 'Lifetime stays';
COMMENT ON COLUMN loyalty_members.status IS 'Membership status';
COMMENT ON TABLE pricing_tiers IS 'Special rates as multipliers of the standard Flexible rate. Only one discount applies to a booking.';
COMMENT ON COLUMN pricing_tiers.pricing_tier_id IS 'PT001-PT010';
COMMENT ON COLUMN pricing_tiers.tier_name IS 'Rate name';
COMMENT ON COLUMN pricing_tiers.description IS 'When it applies';
COMMENT ON COLUMN pricing_tiers.rate_multiplier IS 'Multiplier of the Flexible rate, e.g. 0.85 = 15% off';
COMMENT ON COLUMN pricing_tiers.status IS 'Status';
COMMENT ON TABLE discount_codes IS 'Promotional codes. status is derived on system_date: Expired, Scheduled, Exhausted or Active.';
COMMENT ON COLUMN discount_codes.code_id IS 'DC001-DC029';
COMMENT ON COLUMN discount_codes.discount_code IS 'Code the guest gives, e.g. PEARL100';
COMMENT ON COLUMN discount_codes.discount_type IS 'Percentage or fixed EGP amount';
COMMENT ON COLUMN discount_codes.discount_value IS 'Percent (1-100) or EGP';
COMMENT ON COLUMN discount_codes.usage_count IS 'Times used';
COMMENT ON COLUMN discount_codes.max_usage IS 'Usage limit (NULL = unlimited)';
COMMENT ON COLUMN discount_codes.start_date IS 'First valid day';
COMMENT ON COLUMN discount_codes.end_date IS 'Last valid day';
COMMENT ON COLUMN discount_codes.status IS 'Status on system_date';
COMMENT ON TABLE services IS 'Priced hotel services (breakfast, transfers, spa, laundry, extra bed, late check-out...).';
COMMENT ON COLUMN services.service_id IS 'S001-S016';
COMMENT ON COLUMN services.service_name IS 'Service';
COMMENT ON COLUMN services.category IS 'Category';
COMMENT ON COLUMN services.description IS 'Description';
COMMENT ON COLUMN services.price IS 'Price in EGP (0 = free for guests)';
COMMENT ON COLUMN services.unit IS 'per_person, per_trip, per_kg, per_night...';
COMMENT ON COLUMN services.is_available IS 'Offered now';
COMMENT ON TABLE fees IS 'Fees and percentages from the hotel policies: deposit, smoking fee, early/late check-out, cancellation.';
COMMENT ON COLUMN fees.fee_id IS 'F001-F010';
COMMENT ON COLUMN fees.fee_name IS 'Fee';
COMMENT ON COLUMN fees.amount IS 'Amount in the given unit';
COMMENT ON COLUMN fees.unit IS 'EGP_per_night, percent_of_nightly_rate, nights...';
COMMENT ON COLUMN fees.rule IS 'When it applies';
COMMENT ON TABLE menu_items IS 'In-room dining and restaurant menu. Room service adds the delivery charge of service S002 per order.';
COMMENT ON COLUMN menu_items.item_id IS 'M01-M23';
COMMENT ON COLUMN menu_items.name_en IS 'Dish (English)';
COMMENT ON COLUMN menu_items.name_ar IS 'Dish (Arabic)';
COMMENT ON COLUMN menu_items.category IS 'Starters, Sandwiches, Main courses, Children, Desserts, Drinks';
COMMENT ON COLUMN menu_items.price IS 'Price in EGP, taxes included';
COMMENT ON COLUMN menu_items.dietary IS 'Codes: V vegetarian, G gluten, D dairy, E egg, N nuts, F fish';
COMMENT ON COLUMN menu_items.night_menu IS 'Served 11 PM - 6 AM';
COMMENT ON TABLE bookings IS 'Reservations. Every Pending, Confirmed or Completed booking occupies its room; the database refuses two of them on the same room and nights.';
COMMENT ON COLUMN bookings.booking_id IS 'Booking reference told to the guest: B + 6 digits';
COMMENT ON COLUMN bookings.customer_id IS 'Guest who holds the booking';
COMMENT ON COLUMN bookings.room_number IS 'Assigned room';
COMMENT ON COLUMN bookings.room_type_id IS 'Booked room type (must be the type of the room)';
COMMENT ON COLUMN bookings.check_in IS 'Arrival date (check-in from 3:00 PM)';
COMMENT ON COLUMN bookings.check_out IS 'Departure date (check-out by 12:00 PM)';
COMMENT ON COLUMN bookings.nights IS 'Computed: check_out - check_in';
COMMENT ON COLUMN bookings.adults IS 'Adults';
COMMENT ON COLUMN bookings.children IS 'Children (count toward capacity)';
COMMENT ON COLUMN bookings.booking_status IS 'Pending (waiting for the payment link, room held), Confirmed, Completed, Cancelled, No-show';
COMMENT ON COLUMN bookings.booking_channel IS 'Where it was booked; bookings made by the voice agent use "Voice Agent"';
COMMENT ON COLUMN bookings.rate_plan IS 'Flexible: free cancellation until 48 h before arrival. Non-refundable: 15% cheaper, prepaid, no refund';
COMMENT ON COLUMN bookings.price_per_night IS 'Agreed nightly rate, EGP';
COMMENT ON COLUMN bookings.total_amount IS 'Computed: price_per_night x nights';
COMMENT ON COLUMN bookings.created_at IS 'When the booking was made (set by the API for new bookings; empty in the demo data)';
COMMENT ON COLUMN bookings.cancelled_at IS 'When it was cancelled (set by the API)';
COMMENT ON COLUMN bookings.checked_in_at IS 'Arrival recorded by staff on the dashboard (empty in the demo data)';
COMMENT ON COLUMN bookings.checked_out_at IS 'Departure recorded by staff, with the balance paid at the hotel (empty in the demo data)';
COMMENT ON TABLE payments IS 'One payment record per booking: what was collected and refunded.';
COMMENT ON COLUMN payments.payment_id IS 'P + 6 digits';
COMMENT ON COLUMN payments.booking_id IS 'The booking';
COMMENT ON COLUMN payments.payment_method IS 'Method';
COMMENT ON COLUMN payments.amount_paid IS 'Collected, EGP: Flexible = the first-night deposit until the stay is completed, then the total; Non-refundable = the total (0 when Pending or Failed)';
COMMENT ON COLUMN payments.payment_status IS 'Pending, Paid, Failed, Expired (link not paid in time, booking cancelled), Refunded, Partially Refunded';
COMMENT ON COLUMN payments.payment_due_at IS 'Deadline to pay the link of a Pending booking: 24 h after booking, or 2 h when arrival is less than 24 h away';
COMMENT ON COLUMN payments.refund_amount IS 'Refunded, EGP';
COMMENT ON COLUMN payments.transaction_reference IS 'Gateway reference';
COMMENT ON COLUMN payments.created_at IS 'When it was recorded (set by the API)';
COMMENT ON TABLE customer_requests IS 'Service requests (room service, housekeeping, transfers, changes...). In-stay requests are dated inside the stay; requests without a stay have no booking.';
COMMENT ON COLUMN customer_requests.request_id IS 'REQ + 6 digits';
COMMENT ON COLUMN customer_requests.customer_id IS 'Guest';
COMMENT ON COLUMN customer_requests.booking_id IS 'Related booking (optional)';
COMMENT ON COLUMN customer_requests.request_type IS 'Type';
COMMENT ON COLUMN customer_requests.request_text IS 'What the guest asked';
COMMENT ON COLUMN customer_requests.request_status IS 'Status';
COMMENT ON COLUMN customer_requests.priority IS 'Normal; Urgent = the guest asked for a person and no one was free (Staff Callback); Critical = Emergency';
COMMENT ON COLUMN customer_requests.created_at IS 'When it was made';
COMMENT ON TABLE complaint_tickets IS 'Complaints. Room, service and facility complaints belong to a stay that happened; billing and booking complaints may have no booking.';
COMMENT ON COLUMN complaint_tickets.ticket_id IS 'CMP + 5 digits';
COMMENT ON COLUMN complaint_tickets.customer_id IS 'Guest';
COMMENT ON COLUMN complaint_tickets.booking_id IS 'Related booking (optional)';
COMMENT ON COLUMN complaint_tickets.complaint_type IS 'Type';
COMMENT ON COLUMN complaint_tickets.priority IS 'Priority';
COMMENT ON COLUMN complaint_tickets.description IS 'What went wrong';
COMMENT ON COLUMN complaint_tickets.status IS 'Status';
COMMENT ON COLUMN complaint_tickets.created_at IS 'Opened';
COMMENT ON COLUMN complaint_tickets.resolved_at IS 'Resolved (only for Resolved / Closed)';
COMMENT ON TABLE special_requests IS 'Special requests attached to a booking (celebrations, dietary needs, accessibility, room preferences...).';
COMMENT ON COLUMN special_requests.request_id IS 'SR + 5 digits';
COMMENT ON COLUMN special_requests.customer_id IS 'Guest';
COMMENT ON COLUMN special_requests.booking_id IS 'Booking';
COMMENT ON COLUMN special_requests.request_type IS 'Type';
COMMENT ON COLUMN special_requests.request_text IS 'The request';
COMMENT ON COLUMN special_requests.request_status IS 'Status';
COMMENT ON COLUMN special_requests.created_at IS 'Made';
COMMENT ON COLUMN special_requests.fulfilled_at IS 'Fulfilled (only for Fulfilled)';
COMMENT ON TABLE customer_feedback IS 'Reviews of finished stays: one per booking.';
COMMENT ON COLUMN customer_feedback.feedback_id IS 'FB + 6 digits';
COMMENT ON COLUMN customer_feedback.customer_id IS 'Guest';
COMMENT ON COLUMN customer_feedback.booking_id IS 'Completed booking reviewed';
COMMENT ON COLUMN customer_feedback.feedback_category IS 'What the review is about';
COMMENT ON COLUMN customer_feedback.rating IS '1-5 stars';
COMMENT ON COLUMN customer_feedback.sentiment IS 'From the rating: 4-5 Positive, 3 Neutral, 1-2 Negative';
COMMENT ON COLUMN customer_feedback.feedback_text IS 'Review text';
COMMENT ON COLUMN customer_feedback.feedback_channel IS 'Where it was given';
COMMENT ON COLUMN customer_feedback.would_recommend IS 'Would recommend the hotel';
COMMENT ON TABLE user_accounts IS 'One login for everyone: guests (linked to a customer), hotel staff and admins.';
COMMENT ON COLUMN user_accounts.account_id IS 'Account id';
COMMENT ON COLUMN user_accounts.role IS 'Guest, Staff or Admin';
COMMENT ON COLUMN user_accounts.customer_id IS 'The guest''s customer record (Guest accounts only)';
COMMENT ON COLUMN user_accounts.full_name IS 'Name';
COMMENT ON COLUMN user_accounts.email IS 'Sign-in email; codes and confirmations are sent here';
COMMENT ON COLUMN user_accounts.password_hash IS 'bcrypt hash (never the password itself)';
COMMENT ON COLUMN user_accounts.email_verified IS 'Email confirmed with the code sent at sign-up';
COMMENT ON COLUMN user_accounts.is_active IS 'Can sign in';
COMMENT ON COLUMN user_accounts.created_at IS 'Created';
COMMENT ON COLUMN user_accounts.last_login_at IS 'Last sign-in';
COMMENT ON TABLE booking_links IS 'Bookings made elsewhere (phone, agency, booking platform) that a guest added to the account after the reference check.';
COMMENT ON COLUMN booking_links.account_id IS 'Guest account';
COMMENT ON COLUMN booking_links.booking_id IS 'Booking added';
COMMENT ON COLUMN booking_links.linked_at IS 'When it was added';
COMMENT ON TABLE calls IS 'One row per conversation with the voice agent (voice or text). Filled by the API; shown on the dashboard.';
COMMENT ON COLUMN calls.call_id IS 'Call id';
COMMENT ON COLUMN calls.channel IS 'Voice call or typed chat';
COMMENT ON COLUMN calls.language IS 'Caller''s language';
COMMENT ON COLUMN calls.customer_id IS 'Caller, once identified';
COMMENT ON COLUMN calls.booking_id IS 'Booking discussed, once verified';
COMMENT ON COLUMN calls.identity_verified IS 'Booking reference + last name or phone digits matched';
COMMENT ON COLUMN calls.status IS 'Call status';
COMMENT ON COLUMN calls.escalation_reason IS 'Why it was handed to a person';
COMMENT ON COLUMN calls.assigned_staff_id IS 'Staff account that took the escalated call'; 
COMMENT ON COLUMN calls.summary IS 'Short summary for the dashboard';
COMMENT ON COLUMN calls.started_at IS 'Start';
COMMENT ON COLUMN calls.ended_at IS 'End';
COMMENT ON TABLE call_messages IS 'Every turn of every call: what the guest said (after speech-to-text) and what the agent answered.';
COMMENT ON COLUMN call_messages.message_id IS 'Message id';
COMMENT ON COLUMN call_messages.call_id IS 'Call';
COMMENT ON COLUMN call_messages.turn_no IS 'Order within the call';
COMMENT ON COLUMN call_messages.role IS 'Who spoke';
COMMENT ON COLUMN call_messages.content IS 'Text of the turn';
COMMENT ON COLUMN call_messages.latency_ms IS 'Agent turns: time from the end of the guest turn to the first audio';
COMMENT ON COLUMN call_messages.created_at IS 'Time';
COMMENT ON TABLE call_actions IS 'What the agent did during a call: each tool it ran (availability check, booking lookup, cancellation...) and the result.';
COMMENT ON COLUMN call_actions.action_id IS 'Action id';
COMMENT ON COLUMN call_actions.call_id IS 'Call';
COMMENT ON COLUMN call_actions.tool_name IS 'Tool, e.g. check_availability, quote_cancellation';
COMMENT ON COLUMN call_actions.arguments IS 'Tool input';
COMMENT ON COLUMN call_actions.result IS 'Tool output';
COMMENT ON COLUMN call_actions.success IS 'Did it succeed';
COMMENT ON COLUMN call_actions.booking_id IS 'Booking created, changed or read';
COMMENT ON COLUMN call_actions.created_at IS 'Time';
