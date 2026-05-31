# AI Session Context — TransitFlow

**How to use this file:**
At the start of every AI coding session, paste the full contents of this file as your first message to your AI assistant. This gives the AI the context it needs to produce code that fits your codebase and is consistent with your teammates' work.

**Who maintains this file:**
Whoever makes a schema change or architectural decision updates this file in the same commit. Treat it like a team contract.

---

## Project Overview

TransitFlow is a Python-based AI chat assistant for a fictional transit operator. It queries three databases — PostgreSQL (relational + vector), Neo4j (graph) — and uses an LLM to answer user questions. Our task as students is to design the database schema and implement the query functions in `databases/relational/queries.py` and `databases/graph/queries.py`.

## Tech Stack

- Language: Python 3.11+
- Relational DB: PostgreSQL via `psycopg2` with `RealDictCursor`
- Graph DB: Neo4j via the `neo4j` Python driver
- Vector search: `pgvector` extension (already implemented — do not modify)
- Web UI: Gradio
- LLM: Google Gemini or local Ollama (configured via `.env`)

## Coding Conventions

- **Naming:** `snake_case` for all Python names and SQL identifiers
- **Docstrings:** All functions must have a docstring with `Args:` and `Returns:` sections
- **Return types:** Use type hints. Read-only functions return `list[dict]` or `Optional[dict]`
- **Empty results:** Return `[]` or `None` (as documented), never raise an exception for "not found"
- **SQL:** Use `%s` placeholders for all user inputs — never string-format into SQL
- **Relational pattern:** Use `_connect()` helper + `psycopg2.extras.RealDictCursor`:
  ```python
  with _connect() as conn:
      with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
          cur.execute("SELECT ...", (param,))
          return [dict(row) for row in cur.fetchall()]
  ```
- **Graph pattern:** Use `_driver()` helper + session:
  ```python
  with _driver() as driver:
      with driver.session() as session:
          result = session.run("MATCH ...", station_id=station_id)
          return [dict(record) for record in result]
  ```


## Agreed Relational Schema

```sql
registered_users(user_id, full_name, email, password, phone, date_of_birth, secret_question, secret_answer, registered_at, is_active)

metro_stations(station_id, name, lines, is_interchange_metro, interchange_metro_lines, is_interchange_national_rail, interchange_national_rail_station_id)

national_rail_stations(station_id, name, lines, is_interchange_national_rail, interchange_national_rail_lines, is_interchange_metro, interchange_metro_station_id)

metro_schedules(schedule_id, line, direction, origin_station_id, destination_station_id, first_train_time, last_train_time, base_fare_usd, per_stop_rate_usd, frequency_min, operates_on)

metro_schedule_stops(schedule_id, station_id, stop_order, travel_time_from_origin_min)

national_rail_schedules(schedule_id, line, service_type, direction, origin_station_id, destination_station_id, first_train_time, last_train_time, fare_classes, frequency_min, operates_on)

national_rail_schedule_stops(schedule_id, station_id, stop_order, travel_time_from_origin_min)

national_rail_seat_layouts(layout_id, schedule_id, coaches)

bookings(booking_id, user_id, schedule_id, origin_station_id, destination_station_id, travel_date, departure_time, ticket_type, fare_class, coach, seat_id, stops_travelled, amount_usd, status, booked_at, travelled_at)

metro_travel_history(trip_id, user_id, schedule_id, origin_station_id, destination_station_id, travel_date, ticket_type, stops_travelled, amount_usd, status, purchased_at, travelled_at)

payments(payment_id, booking_id, amount_usd, method, status, paid_at)

feedback(feedback_id, booking_id, user_id, rating, comment, submitted_at)

policy_documents(id, title, category, content, embedding, source_file, created_at)

```

### JSONB Fields

- metro_stations.lines
- metro_stations.interchange_metro_lines
- national_rail_stations.lines
- national_rail_stations.interchange_national_rail_lines
- metro_schedules.operates_on
- national_rail_schedules.fare_classes
- national_rail_schedules.operates_on
- national_rail_seat_layouts.coaches

## Agreed Graph Schema

<!-- ============================================================
  FILL THIS IN after your team agrees on Neo4j node labels and
  relationship types.
  ============================================================ -->

```
Node labels:
:Station (Represents both metro and national rail stations; network type defined by property)

Relationship types:
:CONNECTED_TO (Bidirectional links representing adjacent stations within the same network)

:INTERCHANGE_TO (Bidirectional links representing transfers between metro and national rail networks)

Key properties:
:Station -> station_id (str), name (str), network (str: "metro" | "rail"), lines (list)

:CONNECTED_TO -> travel_time_min (int), line (str), network (str: "metro" | "rail")

:INTERCHANGE_TO -> transfer_time_min (int, hardcoded as 5)

## Function Signatures We Are Implementing

These are fixed contracts. AI-generated code must match these signatures exactly.

### Relational (`databases/relational/queries.py`)

```python
# Read-only
def query_national_rail_availability(origin_id: str, destination_id: str, travel_date: Optional[str] = None) -> list[dict]: ...
def query_national_rail_fare(schedule_id: str, fare_class: str, stops_travelled: int) -> Optional[dict]: ...
def query_metro_schedules(origin_id: str, destination_id: str) -> list[dict]: ...
def query_metro_fare(schedule_id: str, stops_travelled: int) -> Optional[dict]: ...
def query_available_seats(schedule_id: str, travel_date: str, fare_class: str) -> list[dict]: ...
def query_user_profile(user_email: str) -> Optional[dict]: ...
def query_user_bookings(user_email: str) -> dict: ...  # returns {"national_rail": [...], "metro": [...]}
def query_payment_info(booking_id: str) -> Optional[dict]: ...

# Write operations
def execute_booking(user_id, schedule_id, origin_station_id, destination_station_id, travel_date, fare_class, seat_id, ticket_type="single") -> tuple[bool, dict | str]: ...
def execute_cancellation(booking_id: str, user_id: str) -> tuple[bool, dict | str]: ...

# Auth
def register_user(email, first_name, surname, year_of_birth, password, secret_question, secret_answer) -> tuple[bool, str]: ...
def login_user(email: str, password: str) -> Optional[dict]: ...
def get_user_secret_question(email: str) -> Optional[str]: ...
def verify_secret_answer(email: str, answer: str) -> bool: ...
def update_password(email: str, new_password: str) -> bool: ...
```

### Graph (`databases/graph/queries.py`)

```python
def query_shortest_route(origin_id: str, destination_id: str, network: str = "auto") -> dict: ...
def query_cheapest_route(origin_id: str, destination_id: str, network: str = "auto", fare_class: str = "standard") -> dict: ...
def query_alternative_routes(origin_id, destination_id, avoid_station_id, network="auto", max_routes=3) -> list[list[dict]]: ...
def query_interchange_path(origin_id: str, destination_id: str) -> dict: ...
def query_delay_ripple(delayed_station_id: str, hops: int = 2) -> list[dict]: ...
def query_station_connections(station_id: str) -> list[dict]: ...
```

## Team Decisions Log

<!-- Add entries as you make decisions. Format: "Decision: X. Why: Y." -->

- [x] Relational schema is finalized and implemented in `schema.sql`.
- [x] Schedule stop ordering is stored in separate stop tables using `stop_order`.


- [x] Payments table supports both:
  - bookings.booking_id
  - metro_travel_history.trip_id
  via flexible booking_id reference.

- [x] Seat layouts are stored using JSONB
  to support nested coach + seat structures.

- [x] Fare classes are stored as JSONB
  because each schedule may contain
  multiple fare types.

- [x] execute_booking() uses PostgreSQL transaction handling
  with commit / rollback.

- [x] query_payment_info() uses LEFT JOIN
  to support both metro and national rail payments.

- [x] Booking status values are:
  - confirmed
  - cancelled
  - completed

- [x] Payment status values are:
  - pending
  - completed
  - failed
  - paid
  - refunded
- [x] register_user() and update_password() store passwords using salted PBKDF2-HMAC-SHA256 hashes instead of plain text.

- [x] login_user() verifies PBKDF2 password hashes and includes a legacy compatibility path for seeded mock users.

- [x] query_national_rail_availability() calculates available_seats from national_rail_seat_layouts.coaches JSONB minus already-booked seats.

- [x] execute_cancellation() uses a transaction and row locking with FOR UPDATE to prevent duplicate cancellation updates.


## Prompts That Worked

<!-- Share prompts that produced good output so teammates can reuse them. -->

### Query implementation prompt that worked:
```text
Implement this PostgreSQL query function.

Rules:
- Use only the schema provided
- Use only table and column names from the agreed team schema
- Do not invent table names or column names
- Use _connect() helper
- Use psycopg2.extras.RealDictCursor
- Match the function signature exactly
- Do not change parameter names or return types
- Return [] or None for empty results
- Use %s placeholders for SQL parameters
- Never use Python string formatting inside SQL
- Add short comments for important logic only

Schema:
[paste relevant schema from AI_SESSION_CONTEXT.md]

Function:
[paste function stub]
```

## Architecture Notes

TransitFlow uses a hybrid database design:

- PostgreSQL relational tables are used for:
  - bookings
  - payments
  - schedules
  - users

- PostgreSQL JSONB fields are used for:
  - seat layouts
  - fare classes
  - operating days

- Neo4j is used for:
  - route graph traversal
  - shortest path queries
  - interchange analysis


### Booking Workflow

National rail booking flow:

1. Validate schedule route direction
2. Validate seat availability
3. Calculate fare using fare_classes JSONB
4. Find seat coach from seat layout JSONB
5. Insert booking record
6. Insert payment record
7. Commit transaction

Rollback is triggered automatically if any step fails.
