"""
Seed PostgreSQL with all TransitFlow mock data from train-mock-data/.

Usage:
    python skeleton/seed_postgres.py

Run AFTER docker-compose up -d.
You must first design and create your tables in databases/relational/schema.sql.
Safe to re-run: implement your inserts with ON CONFLICT DO NOTHING.
"""

import json
import os
import sys

import psycopg2
from psycopg2.extras import execute_values

# ── resolve paths ────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR    = os.path.join(PROJECT_DIR, "train-mock-data")

sys.path.insert(0, PROJECT_DIR)
from skeleton import config as cfg


def load(filename):
    with open(os.path.join(DATA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


def connect():
    return psycopg2.connect(
        host=cfg.PG_HOST,
        port=cfg.PG_PORT,
        dbname=cfg.PG_DB,
        user=cfg.PG_USER,
        password=cfg.PG_PASSWORD,
    )


def insert_many(cur, table, columns, rows):
    """Bulk insert with ON CONFLICT DO NOTHING. Returns row count inserted."""
    if not rows:
        return 0
    sql = (
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s "
        f"ON CONFLICT DO NOTHING"
    )
    execute_values(cur, sql, rows)
    return cur.rowcount


# ── seeders ──────────────────────────────────────────────────────────────────

def seed_metro_stations(cur):
    data = load("metro_stations.json")

    rows = [
        (
            s["station_id"],
            s["name"],
            json.dumps(s.get("lines", [])),
            s.get("is_interchange_metro", False),
            json.dumps(s.get("interchange_metro_lines")),
            s.get("is_interchange_national_rail", False),
            s.get("interchange_national_rail_station_id"),
        )
        for s in data
    ]

    n = insert_many(
        cur,
        "metro_stations",
        [
            "station_id",
            "name",
            "lines",
            "is_interchange_metro",
            "interchange_metro_lines",
            "is_interchange_national_rail",
            "interchange_national_rail_station_id",
        ],
        rows,
    )
    print(f"  metro_stations: {n} rows")


def seed_national_rail_stations(cur):
    data = load("national_rail_stations.json")

    rows = [
        (
            s["station_id"],
            s["name"],
            json.dumps(s.get("lines", [])),
            s.get("is_interchange_national_rail", False),
            json.dumps(s.get("interchange_national_rail_lines")),
            s.get("is_interchange_metro", False),
            s.get("interchange_metro_station_id"),
        )
        for s in data
    ]

    n = insert_many(
        cur,
        "national_rail_stations",
        [
            "station_id",
            "name",
            "lines",
            "is_interchange_national_rail",
            "interchange_national_rail_lines",
            "is_interchange_metro",
            "interchange_metro_station_id",
        ],
        rows,
    )
    print(f"  national_rail_stations: {n} rows")


def seed_users(cur):
    data = load("registered_users.json")

    rows = [
        (
            u["user_id"],
            u["full_name"],
            u["email"],
            u["password"],
            u.get("phone"),
            u.get("date_of_birth"),
            u.get("secret_question"),
            u.get("secret_answer"),
            u.get("registered_at"),
            u.get("is_active", True),
        )
        for u in data
    ]

    n = insert_many(
        cur,
        "registered_users",
        [
            "user_id",
            "full_name",
            "email",
            "password",
            "phone",
            "date_of_birth",
            "secret_question",
            "secret_answer",
            "registered_at",
            "is_active",
        ],
        rows,
    )
    print(f"  registered_users: {n} rows")


def seed_metro_schedules(cur):
    data = load("metro_schedules.json")

    schedule_rows = []
    stop_rows = []

    for s in data:
        schedule_rows.append((
            s["schedule_id"],
            s["line"],
            s.get("direction"),
            s.get("origin_station_id"),
            s.get("destination_station_id"),
            s.get("first_train_time"),
            s.get("last_train_time"),
            s.get("base_fare_usd"),
            s.get("per_stop_rate_usd"),
            s.get("frequency_min"),
            json.dumps(s.get("operates_on", [])),
        ))

        for index, station_id in enumerate(s.get("stops_in_order", []), start=1):
            stop_rows.append((
                s["schedule_id"],
                station_id,
                index,
                s.get("travel_time_from_origin_min", {}).get(station_id),
            ))

    n1 = insert_many(
        cur,
        "metro_schedules",
        [
            "schedule_id",
            "line",
            "direction",
            "origin_station_id",
            "destination_station_id",
            "first_train_time",
            "last_train_time",
            "base_fare_usd",
            "per_stop_rate_usd",
            "frequency_min",
            "operates_on",
        ],
        schedule_rows,
    )

    n2 = insert_many(
        cur,
        "metro_schedule_stops",
        [
            "schedule_id",
            "station_id",
            "stop_order",
            "travel_time_from_origin_min",
        ],
        stop_rows,
    )

    print(f"  metro_schedules: {n1} rows")
    print(f"  metro_schedule_stops: {n2} rows")


def seed_national_rail_schedules(cur):
    data = load("national_rail_schedules.json")

    schedule_rows = []
    stop_rows = []

    for s in data:
        schedule_rows.append((
            s["schedule_id"],
            s["line"],
            s.get("service_type"),
            s.get("direction"),
            s.get("origin_station_id"),
            s.get("destination_station_id"),
            s.get("first_train_time"),
            s.get("last_train_time"),
            json.dumps(s.get("fare_classes", {})),
            s.get("frequency_min"),
            json.dumps(s.get("operates_on", [])),
        ))

        for index, station_id in enumerate(s.get("stops_in_order", []), start=1):
            stop_rows.append((
                s["schedule_id"],
                station_id,
                index,
                s.get("travel_time_from_origin_min", {}).get(station_id),
            ))

    n1 = insert_many(
        cur,
        "national_rail_schedules",
        [
            "schedule_id",
            "line",
            "service_type",
            "direction",
            "origin_station_id",
            "destination_station_id",
            "first_train_time",
            "last_train_time",
            "fare_classes",
            "frequency_min",
            "operates_on",
        ],
        schedule_rows,
    )

    n2 = insert_many(
        cur,
        "national_rail_schedule_stops",
        [
            "schedule_id",
            "station_id",
            "stop_order",
            "travel_time_from_origin_min",
        ],
        stop_rows,
    )

    print(f"  national_rail_schedules: {n1} rows")
    print(f"  national_rail_schedule_stops: {n2} rows")


def seed_seat_layouts(cur):
    data = load("national_rail_seat_layouts.json")

    rows = [
        (
            s["layout_id"],
            s["schedule_id"],
            json.dumps(s.get("coaches", [])),
        )
        for s in data
    ]

    n = insert_many(
        cur,
        "national_rail_seat_layouts",
        [
            "layout_id",
            "schedule_id",
            "coaches",
        ],
        rows,
    )

    print(f"  national_rail_seat_layouts: {n} rows")


def seed_national_rail_bookings(cur):
    data = load("bookings.json")

    rows = [
        (
            b["booking_id"],
            b["user_id"],
            b["schedule_id"],
            b["origin_station_id"],
            b["destination_station_id"],
            b["travel_date"],
            b["departure_time"],
            b.get("ticket_type"),
            b.get("fare_class"),
            b.get("coach"),
            b.get("seat_id"),
            b.get("stops_travelled"),
            b.get("amount_usd"),
            b.get("status"),
            b.get("booked_at"),
            b.get("travelled_at"),
        )
        for b in data
    ]

    n = insert_many(
        cur,
        "bookings",
        [
            "booking_id",
            "user_id",
            "schedule_id",
            "origin_station_id",
            "destination_station_id",
            "travel_date",
            "departure_time",
            "ticket_type",
            "fare_class",
            "coach",
            "seat_id",
            "stops_travelled",
            "amount_usd",
            "status",
            "booked_at",
            "travelled_at",
        ],
        rows,
    )

    print(f"  bookings: {n} rows")


def seed_metro_travels(cur):
    data = load("metro_travel_history.json")

    rows = [
        (
            t["trip_id"],
            t["user_id"],
            t["schedule_id"],
            t["origin_station_id"],
            t["destination_station_id"],
            t["travel_date"],
            t.get("ticket_type"),
            t.get("stops_travelled"),
            t.get("amount_usd"),
            t.get("status"),
            t.get("purchased_at"),
            t.get("travelled_at"),
        )
        for t in data
    ]

    n = insert_many(
        cur,
        "metro_travel_history",
        [
            "trip_id",
            "user_id",
            "schedule_id",
            "origin_station_id",
            "destination_station_id",
            "travel_date",
            "ticket_type",
            "stops_travelled",
            "amount_usd",
            "status",
            "purchased_at",
            "travelled_at",
        ],
        rows,
    )

    print(f"  metro_travel_history: {n} rows")


def seed_payments(cur):
    data = load("payments.json")

    rows = [
        (
            p["payment_id"],
            p["booking_id"],
            p.get("amount_usd"),
            p.get("method"),
            p.get("status"),
            p.get("paid_at"),
        )
        for p in data
    ]

    n = insert_many(
        cur,
        "payments",
        [
            "payment_id",
            "booking_id",
            "amount_usd",
            "method",
            "status",
            "paid_at",
        ],
        rows,
    )

    print(f"  payments: {n} rows")


def seed_feedback(cur):
    data = load("feedback.json")
    # TODO: Design your table schema, then implement the INSERT logic here.
    pass


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    print("Connecting to PostgreSQL...")
    conn = connect()
    conn.autocommit = False
    cur = conn.cursor()

    try:
        print("Seeding tables (dependency order):")
        seed_metro_stations(cur)
        seed_national_rail_stations(cur)
        seed_metro_schedules(cur)
        seed_national_rail_schedules(cur)
        seed_seat_layouts(cur)
        seed_users(cur)
        seed_national_rail_bookings(cur)
        seed_metro_travels(cur)
        seed_payments(cur)
        seed_feedback(cur)
        conn.commit()
        print("\nAll done. Database seeded successfully.")
    except Exception as e:
        conn.rollback()
        print(f"\nError: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
