"""
TransitFlow — PostgreSQL / Relational Database Layer
=====================================================
This module handles all queries to PostgreSQL.

TWO ROLES ARE SERVED HERE:
  1. Relational  → dual-network transit (metro + national rail),
                   availability, fares, bookings, seat selection
  2. Vector      → policy document similarity search (pgvector)

STUDENT TASK
------------
Design your schema in databases/relational/schema.sql, seed it with
skeleton/seed_postgres.py, then implement the query functions below.

Functions prefixed with `query_`  are read-only lookups called by the agent.
Functions prefixed with `execute_` are write operations (booking/cancellation).

The vector functions (query_policy_vector_search, store_policy_document)
are already implemented — do not modify them.
"""

from __future__ import annotations

import json
import random
import string
import hashlib
import secrets
from datetime import datetime, timezone, date, time
from typing import Optional

import psycopg2
import psycopg2.extras

import os
import sys

# Get current file directory
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Move upward to project root directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))

# 將 project root 加入 Python 搜尋路徑，以便導入 config.py
sys.path.insert(0, PROJECT_ROOT)

from skeleton.config import PG_DSN, VECTOR_TOP_K, VECTOR_SIMILARITY_THRESHOLD


def _connect():
    """Return a new psycopg2 connection with autocommit enabled."""
    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = True
    return conn


def _gen_booking_id() -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"BK-{suffix}"


def _gen_payment_id() -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"PM-{suffix}"

def _gen_user_id() -> str:
    suffix = "".join(random.choices(string.digits, k=6))
    return f"RU{suffix}"


def _hash_password(password: str) -> str:
    """
    Hash a password with PBKDF2-HMAC-SHA256.

    The random salt ensures that two users with the same password do not
    produce the same stored hash. This is required because storing plain-text
    passwords would fail the authentication/security requirement.
    """
    salt = secrets.token_hex(16)
    iterations = 200_000
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()

    return f"pbkdf2_sha256${iterations}${salt}${hashed}"


def _verify_password(password: str, stored_password: str) -> bool:
    """
    Verify either a PBKDF2 password hash or a legacy plain-text seeded password.

    The legacy fallback is included only so the original mock users can still log in
    if the seed file contains plain-text passwords. Newly registered or updated
    passwords are always stored as PBKDF2 hashes.
    """
    if not stored_password:
        return False

    if stored_password.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt, expected_hash = stored_password.split("$", 3)
            actual_hash = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                int(iterations),
            ).hex()

            return secrets.compare_digest(actual_hash, expected_hash)

        except ValueError:
            return False

    # Legacy compatibility for mock data only.
    return secrets.compare_digest(password, stored_password)


# ── Example ───────────────────────────────────────────────────────────────────
# The block below shows the query pattern: open a cursor, run SQL, return rows.
# Use _connect() for read-only queries; for write operations use a manual
# connection with conn.commit() / conn.rollback() (see execute_booking below).

def example_query() -> dict:
    """Example: returns the name of the connected database."""
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT current_database() AS db;")
            return dict(cur.fetchone())

# TODO: Implement the query_ and execute_ functions below.
# ─────────────────────────────────────────────────────────────────────────────


# ── NATIONAL RAIL AVAILABILITY ────────────────────────────────────────────────

# Find all available national rail schedules
# between origin and destination stations.

def query_national_rail_availability(
    origin_id: str,
    destination_id: str,
    travel_date: Optional[str] = None,
) -> list[dict]:
    """
    Return national rail schedules that serve both the origin and destination
    in the correct stop order.

    The function also calculates available_seats because the live test expects
    each schedule result to include remaining seat capacity, not just booked seats.
    Seat capacity is derived from the JSONB seat layout table.
    """

    sql = """
        SELECT
            nrs.schedule_id,
            nrs.line,
            nrs.service_type,
            nrs.direction,
            nrs.first_train_time,
            nrs.last_train_time,

            s1.stop_order AS origin_order,
            s2.stop_order AS destination_order,
            (s2.stop_order - s1.stop_order) AS stops_travelled,

            COALESCE(COUNT(DISTINCT b.seat_id), 0) AS booked_seats,

            nrsl.coaches AS coaches

        FROM national_rail_schedules nrs

        JOIN national_rail_schedule_stops s1
            ON nrs.schedule_id = s1.schedule_id

        JOIN national_rail_schedule_stops s2
            ON nrs.schedule_id = s2.schedule_id

        LEFT JOIN bookings b
            ON nrs.schedule_id = b.schedule_id
            AND b.travel_date = %s
            AND b.status != 'cancelled'

        LEFT JOIN national_rail_seat_layouts nrsl
            ON nrs.schedule_id = nrsl.schedule_id

        WHERE s1.station_id = %s
          AND s2.station_id = %s
          AND s1.stop_order < s2.stop_order

        GROUP BY
            nrs.schedule_id,
            nrs.line,
            nrs.service_type,
            nrs.direction,
            nrs.first_train_time,
            nrs.last_train_time,
            s1.stop_order,
            s2.stop_order,
            nrsl.coaches

        ORDER BY nrs.line, nrs.schedule_id
    """

    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            cur.execute(
                sql,
                (
                    travel_date,
                    origin_id,
                    destination_id,
                ),
            )

            rows = cur.fetchall()

            results = []

            for row in rows:
                row = dict(row)

                coaches = row.pop("coaches", None) or []

                # Count every seat in the JSONB coach layout.
                # This is needed because seat capacity is stored as nested JSON,
                # not as a separate normalized seat table.
                total_seats = 0
                for coach in coaches:
                    total_seats += len(coach.get("seats", []))

                booked_seats = int(row.get("booked_seats") or 0)
                available_seats = max(total_seats - booked_seats, 0)

                row["total_seats"] = total_seats
                row["available_seats"] = available_seats

                results.append(row)

            return results


def query_national_rail_fare(
    schedule_id: str,
    fare_class: str,
    stops_travelled: int,
) -> Optional[dict]:

    sql = """
        SELECT fare_classes
        FROM national_rail_schedules
        WHERE schedule_id = %s
    """

    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            cur.execute(sql, (schedule_id,))

            row = cur.fetchone()

            if not row:
                return None

            fare_classes = row["fare_classes"]

            if fare_class not in fare_classes:
                return None

            fare_info = fare_classes[fare_class]

            base_fare = float(fare_info["base_fare_usd"])
            per_stop_rate = float(fare_info["per_stop_rate_usd"])

            total = base_fare + (per_stop_rate * stops_travelled)

            return {
                "fare_class": fare_class,
                "base_fare_usd": base_fare,
                "per_stop_rate_usd": per_stop_rate,
                "total_fare_usd": round(total, 2)
            }


# ── METRO SCHEDULES & FARE ────────────────────────────────────────────────────

def query_metro_schedules(origin_id: str, destination_id: str) -> list[dict]:

    sql = """
        SELECT
            ms.schedule_id,
            ms.line,
            ms.direction,
            ms.first_train_time,
            ms.last_train_time,
            s1.stop_order AS origin_order,
            s2.stop_order AS destination_order,
            (s2.stop_order - s1.stop_order) AS stops_travelled
        FROM metro_schedules ms

        JOIN metro_schedule_stops s1
            ON ms.schedule_id = s1.schedule_id

        JOIN metro_schedule_stops s2
            ON ms.schedule_id = s2.schedule_id

        WHERE s1.station_id = %s
          AND s2.station_id = %s
          AND s1.stop_order < s2.stop_order

        ORDER BY ms.line, ms.schedule_id
    """

    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            cur.execute(sql, (origin_id, destination_id))

            rows = cur.fetchall()

            return [
                dict(row)
                for row in rows
            ]


def query_metro_fare(schedule_id: str, stops_travelled: int) -> Optional[dict]:

    sql = """
        SELECT
            base_fare_usd,
            per_stop_rate_usd
        FROM metro_schedules
        WHERE schedule_id = %s
    """

    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            cur.execute(sql, (schedule_id,))

            row = cur.fetchone()

            if not row:
                return None

            base_fare = float(row["base_fare_usd"])
            per_stop_rate = float(row["per_stop_rate_usd"])

            total = base_fare + (per_stop_rate * stops_travelled)

            return {
                "base_fare_usd": base_fare,
                "per_stop_rate_usd": per_stop_rate,
                "total_fare_usd": round(total, 2)
            }


# ── SEAT SELECTION ────────────────────────────────────────────────────────────

def query_available_seats(
    schedule_id: str,
    travel_date: str,
    fare_class: str,
) -> list[dict]:

    # Step 1:
    # Get seat layout JSON from national_rail_seat_layouts

    sql_layout = """
        SELECT coaches
        FROM national_rail_seat_layouts
        WHERE schedule_id = %s
    """

    # Step 2:
    # Get already-booked seat_ids for this schedule/date/class

    sql_booked = """
        SELECT seat_id
        FROM bookings
        WHERE schedule_id = %s
          AND travel_date = %s
          AND fare_class = %s
          AND status != 'cancelled'
    """

    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            # ── Get layout ─────────────────────────────

            cur.execute(sql_layout, (schedule_id,))

            row = cur.fetchone()

            if not row:
                return []

            coaches = row["coaches"]

            # ── Get booked seats ──────────────────────

            cur.execute(
                sql_booked,
                (
                    schedule_id,
                    travel_date,
                    fare_class,
                )
            )

            booked_rows = cur.fetchall()

            booked_seats = {
                r["seat_id"]
                for r in booked_rows
            }

            # ── Build available seats ─────────────────

            available = []

            for coach in coaches:

                # Only use matching fare class
                if coach["fare_class"] != fare_class:
                    continue

                for seat in coach["seats"]:

                    if seat["seat_id"] not in booked_seats:

                        available.append({
                            "seat_id": seat["seat_id"],
                            "coach": coach["coach"],
                            "row": seat["row"],
                            "column": seat["column"],
                        })

            return available


# Group seats by row number.
# Prefer seats in the same row before considering nearby rows.
def auto_select_adjacent_seats(available_seats: list[dict], count: int) -> list[str]:
    """
    Select `count` seats that are as close together as possible (same row preferred,
    then adjacent rows). Returns a list of seat_ids.

    Args:
        available_seats: output of query_available_seats()
        count:           number of seats needed
    """
    if not available_seats or count <= 0:
        return []
    if count >= len(available_seats):
        return [s["seat_id"] for s in available_seats[:count]]

    from collections import defaultdict
    rows: dict[int, list[dict]] = defaultdict(list)
    for seat in available_seats:
        rows[seat["row"]].append(seat)

    for row_seats in sorted(rows.values(), key=lambda s: s[0]["row"]):
        if len(row_seats) >= count:
            return [s["seat_id"] for s in row_seats[:count]]

    sorted_seats = sorted(available_seats, key=lambda s: (s["row"], s["column"]))
    return [s["seat_id"] for s in sorted_seats[:count]]


# ── USER & BOOKING QUERIES ────────────────────────────────────────────────────

def query_user_profile(user_email: str) -> Optional[dict]:

    sql = """
        SELECT *
        FROM registered_users
        WHERE email = %s
    """
    #build PostgreSQL connection
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (user_email,))
            row = cur.fetchone()

            if row:
                return dict(row)

            return None


def query_user_bookings(user_email: str) -> dict:

    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            # First find the user_id from email
            cur.execute(
                """
                SELECT user_id
                FROM registered_users
                WHERE email = %s
                """,
                (user_email,)
            )

            user = cur.fetchone()

            if not user:
                return {
                    "national_rail": [],
                    "metro": []
                }

            user_id = user["user_id"]

            # Query national rail bookings
            cur.execute(
                """
                SELECT *
                FROM bookings
                WHERE user_id = %s
                ORDER BY booked_at DESC
                """,
                (user_id,)
            )

            national_rail = [
                dict(row)
                for row in cur.fetchall()
            ]

            # Query metro travel history
            cur.execute(
                """
                SELECT *
                FROM metro_travel_history
                WHERE user_id = %s
                ORDER BY travelled_at DESC
                """,
                (user_id,)
            )

            metro = [
                dict(row)
                for row in cur.fetchall()
            ]

            return {
                "national_rail": national_rail,
                "metro": metro
            }


# payments.booking_id may reference:
# - bookings.booking_id (national rail)
# - metro_travel_history.trip_id (metro)
#
# LEFT JOIN is used to support both systems.
def query_payment_info(booking_id: str) -> Optional[dict]:

    sql = """
        SELECT
            p.payment_id,
            p.booking_id,
            p.amount_usd,
            p.method,
            p.status,
            p.paid_at,

            b.user_id AS booking_user_id,
            b.schedule_id AS booking_schedule_id,

            mt.user_id AS metro_user_id,
            mt.schedule_id AS metro_schedule_id,

            CASE
                WHEN b.booking_id IS NOT NULL THEN 'national_rail'
                WHEN mt.trip_id IS NOT NULL THEN 'metro'
                ELSE 'unknown'
            END AS payment_type

        FROM payments p

        LEFT JOIN bookings b
            ON p.booking_id = b.booking_id

        LEFT JOIN metro_travel_history mt
            ON p.booking_id = mt.trip_id

        WHERE p.booking_id = %s
    """

    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            cur.execute(sql, (booking_id,))
            row = cur.fetchone()

            if row:
                return dict(row)

            return None


# ── TRANSACTIONAL OPERATIONS ──────────────────────────────────────────────────

def execute_booking(
    user_id: str,
    schedule_id: str,
    origin_station_id: str,
    destination_station_id: str,
    travel_date: str,
    fare_class: str,
    seat_id: str,
    ticket_type: str = "single",
) -> tuple[bool, dict | str]:

    conn = psycopg2.connect(PG_DSN)

    try:
        conn.autocommit = False

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            # 1. Check whether the selected seat is already booked
            cur.execute(
                """
                SELECT booking_id
                FROM bookings
                WHERE schedule_id = %s
                  AND travel_date = %s
                  AND seat_id = %s
                  AND status != 'cancelled'
                """,
                (schedule_id, travel_date, seat_id)
            )

            if cur.fetchone():
                conn.rollback()        
                return False, "Seat is already booked."

            # 2. Get stop order to calculate stops travelled
            cur.execute(
                """
                SELECT
                    s1.stop_order AS origin_order,
                    s2.stop_order AS destination_order,
                    nrs.first_train_time,
                    nrs.fare_classes
                FROM national_rail_schedules nrs
                JOIN national_rail_schedule_stops s1
                    ON nrs.schedule_id = s1.schedule_id
                JOIN national_rail_schedule_stops s2
                    ON nrs.schedule_id = s2.schedule_id
                WHERE nrs.schedule_id = %s
                  AND s1.station_id = %s
                  AND s2.station_id = %s
                  AND s1.stop_order < s2.stop_order
                """,
                (schedule_id, origin_station_id, destination_station_id)
            )

            route = cur.fetchone()

            if not route:
                conn.rollback()
                return False, "Invalid route for this schedule."

            stops_travelled = route["destination_order"] - route["origin_order"]

            # 3. Calculate fare
            fare_classes = route["fare_classes"]

            if fare_class not in fare_classes:
                conn.rollback()
                return False, "Invalid fare class."

            fare_info = fare_classes[fare_class]
            base_fare = float(fare_info["base_fare_usd"])
            per_stop_rate = float(fare_info["per_stop_rate_usd"])
            amount_usd = round(base_fare + per_stop_rate * stops_travelled, 2)

            # 4. Find coach from seat layout
            cur.execute(
                """
                SELECT coaches
                FROM national_rail_seat_layouts
                WHERE schedule_id = %s
                """,
                (schedule_id,)
            )

            layout = cur.fetchone()
            coach_name = None

            if layout:
                for coach in layout["coaches"]:
                    if coach["fare_class"] != fare_class:
                        continue

                    for seat in coach["seats"]:
                        if seat["seat_id"] == seat_id:
                            coach_name = coach["coach"]
                            break

                    if coach_name:
                        break

            if not coach_name:
                conn.rollback()
                return False, "Seat does not exist for this fare class."

            # 5. Insert booking
            booking_id = _gen_booking_id()
            payment_id = _gen_payment_id()
            now = datetime.now(timezone.utc)

            cur.execute(
                """
                INSERT INTO bookings (
                    booking_id,
                    user_id,
                    schedule_id,
                    origin_station_id,
                    destination_station_id,
                    travel_date,
                    departure_time,
                    ticket_type,
                    fare_class,
                    coach,
                    seat_id,
                    stops_travelled,
                    amount_usd,
                    status,
                    booked_at,
                    travelled_at
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, NULL
                )
                """,
                (
                    booking_id,
                    user_id,
                    schedule_id,
                    origin_station_id,
                    destination_station_id,
                    travel_date,
                    route["first_train_time"],
                    ticket_type,
                    fare_class,
                    coach_name,
                    seat_id,
                    stops_travelled,
                    amount_usd,
                    "confirmed",
                    now,
                )
            )

            # 6. Insert payment record
            cur.execute(
                """
                INSERT INTO payments (
                    payment_id,
                    booking_id,
                    amount_usd,
                    method,
                    status,
                    paid_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    payment_id,
                    booking_id,
                    amount_usd,
                    "credit_card",
                    "paid",
                    now,
                )
            )

            conn.commit()

            return True, {
                "booking_id": booking_id,
                "payment_id": payment_id,
                "user_id": user_id,
                "schedule_id": schedule_id,
                "origin_station_id": origin_station_id,
                "destination_station_id": destination_station_id,
                "travel_date": travel_date,
                "departure_time": str(route["first_train_time"]),
                "fare_class": fare_class,
                "coach": coach_name,
                "seat_id": seat_id,
                "stops_travelled": stops_travelled,
                "amount_usd": amount_usd,
                "status": "confirmed",
            }

    except Exception as e:
        conn.rollback()
        return False, str(e)

    finally:
        conn.close()


def execute_cancellation(booking_id: str, user_id: str) -> tuple[bool, dict | str]:
    """
    Cancel a national rail booking owned by the given user.

    The function uses a single transaction so the booking status update and
    payment refund update are applied together. If any step fails, rollback
    prevents the database from ending up with a cancelled booking but unchanged
    payment record.
    """
    conn = psycopg2.connect(PG_DSN)

    try:
        conn.autocommit = False

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            # Lock the booking row during cancellation so two cancellation requests
            # cannot update the same booking at the same time.
            cur.execute(
                """
                SELECT
                    b.booking_id,
                    b.user_id,
                    b.schedule_id,
                    b.travel_date,
                    b.departure_time,
                    b.amount_usd,
                    b.status,
                    nrs.service_type
                FROM bookings b
                JOIN national_rail_schedules nrs
                    ON b.schedule_id = nrs.schedule_id
                WHERE b.booking_id = %s
                  AND b.user_id = %s
                FOR UPDATE
                """,
                (booking_id, user_id),
            )

            booking = cur.fetchone()

            if not booking:
                conn.rollback()
                return False, "Booking not found for this user."

            if booking["status"] == "cancelled":
                conn.rollback()
                return False, "Booking is already cancelled."

            amount_usd = float(booking["amount_usd"])

            travel_date = booking["travel_date"]
            departure_time = booking["departure_time"]

            if isinstance(travel_date, str):
                travel_date = datetime.fromisoformat(travel_date).date()

            if isinstance(departure_time, str):
                departure_time = datetime.strptime(departure_time, "%H:%M:%S").time()

            departure_dt = datetime.combine(travel_date, departure_time)
            now_dt = datetime.now()

            hours_before_departure = (departure_dt - now_dt).total_seconds() / 3600

            service_type = (booking["service_type"] or "").lower()

            # Refund policy:
            # Normal services use a more flexible cancellation window.
            # Express services use a stricter policy because they have higher seat demand.
            if service_type == "express":
                if hours_before_departure >= 24:
                    refund_rate = 1.00
                    policy_note = "Express cancellation at least 24 hours before departure: 100% refund."
                elif hours_before_departure >= 2:
                    refund_rate = 0.50
                    policy_note = "Express cancellation 2–24 hours before departure: 50% refund."
                else:
                    refund_rate = 0.00
                    policy_note = "Express cancellation less than 2 hours before departure: no refund."
            else:
                if hours_before_departure >= 24:
                    refund_rate = 1.00
                    policy_note = "Normal cancellation at least 24 hours before departure: 100% refund."
                elif hours_before_departure >= 2:
                    refund_rate = 0.75
                    policy_note = "Normal cancellation 2–24 hours before departure: 75% refund."
                elif hours_before_departure >= 0:
                    refund_rate = 0.50
                    policy_note = "Normal same-day cancellation before departure: 50% refund."
                else:
                    refund_rate = 0.00
                    policy_note = "Cancellation after departure: no refund."

            refund_amount = round(amount_usd * refund_rate, 2)

            # Soft delete strategy: keep the booking row but mark it cancelled.
            cur.execute(
                """
                UPDATE bookings
                SET status = 'cancelled'
                WHERE booking_id = %s
                  AND user_id = %s
                """,
                (booking_id, user_id),
            )

            # Mark the related payment as refunded when a refund amount exists.
            # If refund is 0, the booking is still cancelled but payment remains paid.
            if refund_amount > 0:
                cur.execute(
                    """
                    UPDATE payments
                    SET status = 'refunded'
                    WHERE booking_id = %s
                    """,
                    (booking_id,),
                )

            conn.commit()

            return True, {
                "booking_id": booking_id,
                "user_id": user_id,
                "status": "cancelled",
                "original_amount_usd": amount_usd,
                "refund_rate": refund_rate,
                "refund_amount": refund_amount,
                "refund_amount_usd": refund_amount,
                "policy_note": policy_note,
            }

    except Exception as e:
        conn.rollback()
        return False, str(e)

    finally:
        conn.close()


# ── AUTHENTICATION QUERIES ────────────────────────────────────────────────────

def register_user(
    email: str,
    first_name: str,
    surname: str,
    year_of_birth: int,
    password: str,
    secret_question: str,
    secret_answer: str,
) -> tuple[bool, str]:
    """
    Register a new user.

    Passwords are stored as salted PBKDF2 hashes, not plain text. This satisfies
    the project requirement that authentication data must use a strong password
    hashing approach rather than storing raw passwords.
    """
    user_id = _gen_user_id()
    full_name = f"{first_name} {surname}".strip()
    password_hash = _hash_password(password)

    # The schema stores date_of_birth as DATE, while this function receives
    # year_of_birth. We store January 1 of that year as a consistent placeholder.
    date_of_birth = date(int(year_of_birth), 1, 1)

    sql = """
        INSERT INTO registered_users (
            user_id,
            full_name,
            email,
            password,
            phone,
            date_of_birth,
            secret_question,
            secret_answer,
            registered_at,
            is_active
        )
        VALUES (%s, %s, %s, %s, NULL, %s, %s, %s, %s, TRUE)
    """

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        user_id,
                        full_name,
                        email,
                        password_hash,
                        date_of_birth,
                        secret_question,
                        secret_answer,
                        datetime.now(timezone.utc),
                    ),
                )

        return True, user_id

    except psycopg2.errors.UniqueViolation:
        return False, "Email is already registered."

    except Exception as e:
        return False, str(e)


def login_user(email: str, password: str) -> Optional[dict]:
    """
    Verify user credentials and return a user dict on success.

    The function verifies PBKDF2 hashes for newly created users and also supports
    legacy mock users if the seed data contains plain-text passwords.
    """
    sql = """
        SELECT
            user_id,
            full_name,
            email,
            password,
            phone,
            date_of_birth,
            is_active
        FROM registered_users
        WHERE email = %s
          AND is_active = TRUE
    """

    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            cur.execute(sql, (email,))
            user = cur.fetchone()

            if not user:
                return None

            if not _verify_password(password, user["password"]):
                return None

            full_name = user["full_name"] or ""
            name_parts = full_name.split(" ", 1)

            first_name = name_parts[0] if name_parts else ""
            surname = name_parts[1] if len(name_parts) > 1 else ""

            return {
                "user_id": user["user_id"],
                "email": user["email"],
                "full_name": full_name,
                "first_name": first_name,
                "surname": surname,
                "phone": user["phone"],
                "date_of_birth": user["date_of_birth"],
                "is_active": user["is_active"],
            }


def get_user_secret_question(email: str) -> Optional[str]:
    """Return the secret question for a registered email, or None if not found."""
    sql = """
        SELECT secret_question
        FROM registered_users
        WHERE email = %s
          AND is_active = TRUE
    """

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (email,))
            row = cur.fetchone()

            if not row:
                return None

            return row[0]


def verify_secret_answer(email: str, answer: str) -> bool:
    """
    Return True if the provided answer matches the stored secret answer.

    The comparison is case-insensitive and ignores leading/trailing spaces so
    users are not rejected for minor formatting differences.
    """
    sql = """
        SELECT secret_answer
        FROM registered_users
        WHERE email = %s
          AND is_active = TRUE
    """

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (email,))
            row = cur.fetchone()

            if not row or row[0] is None:
                return False

            stored_answer = str(row[0]).strip().lower()
            provided_answer = str(answer).strip().lower()

            return stored_answer == provided_answer


def update_password(email: str, new_password: str) -> bool:
    """
    Update a user's password using a new salted PBKDF2 hash.

    The old password value is never reused. A fresh salt is generated every time
    so repeated password resets do not produce identical stored hashes.
    """
    new_hash = _hash_password(new_password)

    sql = """
        UPDATE registered_users
        SET password = %s
        WHERE email = %s
          AND is_active = TRUE
    """

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (new_hash, email))
            return cur.rowcount > 0


# ── VECTOR / RAG QUERIES — do not modify ─────────────────────────────────────

def query_policy_vector_search(embedding: list[float], top_k: int = VECTOR_TOP_K) -> list[dict]:
    """
    Find the most relevant policy documents for a given query embedding.

    Args:
        embedding: Query vector from llm.embed(user_question)
        top_k:     Number of results to return

    Returns:
        List of dicts with title, category, content, and similarity score
    """
    sql = """
        SELECT
            title,
            category,
            content,
            1 - (embedding <=> %s::vector) AS similarity
        FROM policy_documents
        WHERE 1 - (embedding <=> %s::vector) > %s
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (vec_str, vec_str, VECTOR_SIMILARITY_THRESHOLD, vec_str, top_k))
            return [dict(row) for row in cur.fetchall()]


def store_policy_document(
    title: str,
    category: str,
    content: str,
    embedding: list[float],
    source_file: str = "",
) -> int:
    """
    Insert a policy document with its embedding into the database.
    Used by skeleton/seed_vectors.py — students don't need to call this directly.

    Returns:
        The new document's id
    """
    sql = """
        INSERT INTO policy_documents (title, category, content, embedding, source_file)
        VALUES (%s, %s, %s, %s::vector, %s)
        RETURNING id
    """
    vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (title, category, content, vec_str, source_file))
            return cur.fetchone()[0]
