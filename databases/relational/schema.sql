-- ============================================================
--  TransitFlow PostgreSQL Schema
--  Seed data is loaded separately by: python skeleton/seed_postgres.py
--
--  TWO ROLES:
--    1. Relational  → dual-network transit data you design below
--    2. Vector      → policy documents for RAG (provided — do not modify)
-- ============================================================

-- ============================================================
--  STUDENT TASK — Design and create your relational tables here
--
--  Start from the mock data in train-mock-data/:
--    metro_stations.json, national_rail_stations.json
--    metro_schedules.json, national_rail_schedules.json
--    national_rail_seat_layouts.json
--    registered_users.json
--    bookings.json, metro_travel_history.json
--    payments.json, feedback.json
--
--  Think about:
--    - What tables do you need?
--    - What columns and data types?
--    - Which fields are primary keys? Which are foreign keys?
--    - What constraints make sense?
--
--  Apply your schema with:
--    docker-compose down -v && docker-compose up -d
-- ============================================================
CREATE TABLE registered_users (
    user_id VARCHAR(10) PRIMARY KEY,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    phone TEXT,
    date_of_birth DATE,
    secret_question TEXT,
    secret_answer TEXT,
    registered_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE metro_stations (
    station_id VARCHAR(10) PRIMARY KEY,
    name TEXT NOT NULL,
    lines JSONB NOT NULL,
    is_interchange_metro BOOLEAN DEFAULT FALSE,
    interchange_metro_lines JSONB,
    is_interchange_national_rail BOOLEAN DEFAULT FALSE,
    interchange_national_rail_station_id VARCHAR(10)
);

CREATE TABLE national_rail_stations (
    station_id VARCHAR(10) PRIMARY KEY,
    name TEXT NOT NULL,
    lines JSONB NOT NULL,
    is_interchange_national_rail BOOLEAN DEFAULT FALSE,
    interchange_national_rail_lines JSONB,
    is_interchange_metro BOOLEAN DEFAULT FALSE,
    interchange_metro_station_id VARCHAR(10)
);

CREATE TABLE metro_schedules (
    schedule_id VARCHAR(20) PRIMARY KEY,
    line VARCHAR(10) NOT NULL,
    direction VARCHAR(20),
    origin_station_id VARCHAR(10) REFERENCES metro_stations(station_id),
    destination_station_id VARCHAR(10) REFERENCES metro_stations(station_id),
    first_train_time TIME,
    last_train_time TIME,
    base_fare_usd NUMERIC(10,2),
    per_stop_rate_usd NUMERIC(10,2),
    frequency_min INT CHECK (frequency_min > 0),
    operates_on JSONB
);

CREATE TABLE metro_schedule_stops (
    schedule_id VARCHAR(20) REFERENCES metro_schedules(schedule_id),
    station_id VARCHAR(10) REFERENCES metro_stations(station_id),
    stop_order INT NOT NULL,
    travel_time_from_origin_min INT,
    PRIMARY KEY (schedule_id, station_id)
);

CREATE TABLE national_rail_schedules (
    schedule_id VARCHAR(20) PRIMARY KEY,
    line VARCHAR(10) NOT NULL,
    service_type VARCHAR(20),
    direction VARCHAR(20),
    origin_station_id VARCHAR(10) REFERENCES national_rail_stations(station_id),
    destination_station_id VARCHAR(10) REFERENCES national_rail_stations(station_id),
    first_train_time TIME,
    last_train_time TIME,
    fare_classes JSONB,
    frequency_min INT CHECK (frequency_min > 0),
    operates_on JSONB
);

CREATE TABLE national_rail_schedule_stops (
    schedule_id VARCHAR(20) REFERENCES national_rail_schedules(schedule_id),
    station_id VARCHAR(10) REFERENCES national_rail_stations(station_id),
    stop_order INT NOT NULL,
    travel_time_from_origin_min INT,
    PRIMARY KEY (schedule_id, station_id)
);

CREATE TABLE bookings (
    booking_id VARCHAR(20) PRIMARY KEY,
    user_id VARCHAR(10) REFERENCES registered_users(user_id),
    schedule_id VARCHAR(20) REFERENCES national_rail_schedules(schedule_id),
    origin_station_id VARCHAR(10)
        REFERENCES national_rail_stations(station_id),

    destination_station_id VARCHAR(10) REFERENCES national_rail_stations(station_id),
    travel_date DATE,
    departure_time TIME,
    ticket_type VARCHAR(30),
    fare_class VARCHAR(30),
    coach VARCHAR(10),
    seat_id VARCHAR(10),
    stops_travelled INT,
    amount_usd NUMERIC(10,2) CHECK (amount_usd >= 0),
    status VARCHAR(30) CHECK (status IN ('confirmed', 'cancelled', 'completed')),
    booked_at TIMESTAMPTZ,
    travelled_at TIMESTAMPTZ
);

CREATE TABLE metro_travel_history (
    trip_id VARCHAR(20) PRIMARY KEY,
    user_id VARCHAR(10) REFERENCES registered_users(user_id),
    schedule_id VARCHAR(20) REFERENCES metro_schedules(schedule_id),
    origin_station_id VARCHAR(10) REFERENCES metro_stations(station_id),
    destination_station_id VARCHAR(10) REFERENCES metro_stations(station_id),
    travel_date DATE NOT NULL,
    ticket_type VARCHAR(30),
    stops_travelled INT,
    amount_usd NUMERIC(10,2) NOT NULL CHECK (amount_usd >= 0),
    status VARCHAR(30) CHECK (status IN ('confirmed', 'cancelled', 'completed')),
    purchased_at TIMESTAMPTZ,
    travelled_at TIMESTAMPTZ
);

CREATE TABLE payments (
    payment_id VARCHAR(20) PRIMARY KEY,
    booking_id VARCHAR(20) REFERENCES bookings(booking_id),
    amount_usd NUMERIC(10,2) NOT NULL CHECK (amount_usd >= 0),
    method VARCHAR(30),
    status VARCHAR(30) CHECK (status IN ('pending', 'completed', 'failed', 'paid')),
    paid_at TIMESTAMPTZ
);

CREATE TABLE feedback (
    feedback_id VARCHAR(20) PRIMARY KEY,
    booking_id VARCHAR(20) REFERENCES bookings(booking_id),
    user_id VARCHAR(10) REFERENCES registered_users(user_id),
    rating INT CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    submitted_at TIMESTAMPTZ
);

CREATE TABLE national_rail_seat_layouts (
    layout_id VARCHAR(20) PRIMARY KEY,
    schedule_id VARCHAR(20) REFERENCES national_rail_schedules(schedule_id),
    coaches JSONB NOT NULL
);

CREATE TABLE ticket_types (
    ticket_type VARCHAR(30) PRIMARY KEY,
    display_name TEXT,
    available_on JSONB,
    description TEXT,
    metro JSONB,
    national_rail JSONB
);

CREATE TABLE refund_policies (
    policy_id VARCHAR(20) PRIMARY KEY,
    label TEXT,
    applies_to JSONB,
    cancellation_windows JSONB,
    return_ticket_notes TEXT,
    no_show_policy TEXT
);

CREATE TABLE booking_rules (
    version VARCHAR(20) PRIMARY KEY,
    last_updated DATE,
    national_rail JSONB,
    metro JSONB,
    general_rules JSONB
);

CREATE TABLE travel_policies (
    version VARCHAR(20) PRIMARY KEY,
    last_updated DATE,
    metro JSONB,
    national_rail JSONB
);



-- ============================================================
--  VECTOR SCHEMA  (RAG / Help Desk) — do not modify
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS policy_documents (
    id          SERIAL       PRIMARY KEY,
    title       VARCHAR(200) NOT NULL,
    category    VARCHAR(50)  NOT NULL,  -- 'refund', 'booking', 'conduct'
    content     TEXT         NOT NULL,
    -- 768-dim  → Ollama nomic-embed-text (default)
    -- 3072-dim → Gemini gemini-embedding-001
    -- If you switch LLM_PROVIDER to gemini, change to vector(3072) and reset the database.
    embedding   vector(768),
    source_file VARCHAR(200),
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- Index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS policy_documents_embedding_idx
ON policy_documents USING hnsw (embedding vector_cosine_ops);
