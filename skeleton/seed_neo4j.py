"""
TransitFlow — Neo4j Seeder
Run once after starting Docker:
    python skeleton/seed_neo4j.py

Loads station and network data from train-mock-data/:
  - metro_stations.json         — city metro stations and adjacencies
  - national_rail_stations.json — national rail stations and adjacencies

Design your graph schema (node labels, relationship types, properties)
based on the data in these files, then implement the seed() function below.
"""
import json
import os
import sys

# Ensure project root is in Python path so we can import skeleton modules
sys.path.insert(0, ".")

from neo4j import GraphDatabase
from skeleton.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


# Path to mock data folder (relative to this file)
_DATA_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "train-mock-data")
)


def _load(filename):
    # Load JSON file from train-mock-data directory
    with open(os.path.join(_DATA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


def seed():
    # Load station datasets (metro + national rail)
    metro_stations = _load("metro_stations.json")
    rail_stations  = _load("national_rail_stations.json")

    # Connect to Neo4j database
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    with driver.session() as session:

        # Clear existing graph data before seeding
        session.run("MATCH (n) DETACH DELETE n")
        print("   Cleared existing graph data")

        # ─────────────────────────────────────────────
        # CREATE METRO STATION NODES
        # ─────────────────────────────────────────────

        for s in metro_stations:
            session.run("""
                MERGE (station:Metro {station_id: $id})
                SET station.name = $name,
                    station.network = 'metro',
                    station.lines = $lines,
                    station.line_id = $primary_line
            """, {
                "id": s["station_id"],
                "name": s["name"],
                "lines": s.get("lines", []),
                "primary_line": s.get("lines", [""])[0] if s.get("lines") else ""
            })

        print(f"   Created {len(metro_stations)} metro stations (with :Metro label)")

        # ─────────────────────────────────────────────
        # CREATE NATIONAL RAIL STATION NODES
        # ─────────────────────────────────────────────

        for s in rail_stations:
            session.run("""
                MERGE (station:Rail {station_id: $id})
                SET station.name = $name,
                    station.network = 'rail',
                    station.lines = $lines,
                    station.line_id = $primary_line
            """, {
                "id": s["station_id"],
                "name": s["name"],
                "lines": s.get("lines", []),
                "primary_line": s.get("lines", [""])[0] if s.get("lines") else ""
            })

        print(f"   Created {len(rail_stations)} rail stations (with :Rail label)")

        # ─────────────────────────────────────────────
        # CREATE METRO CONNECTIONS (CONNECTED_TO relationships)
        # ─────────────────────────────────────────────

        for s in metro_stations:
            for adj in s.get("adjacent_stations", []):

                session.run("""
                    MATCH (a:Metro {station_id: $from})
                    MATCH (b:Metro {station_id: $to})

                    // Create directed relationship between metro stations
                    MERGE (a)-[r:CONNECTED_TO {from_id: $from, to_id: $to}]->(b)

                    SET r.travel_time_min = $time,
                        r.line_id = $line,
                        r.network = 'metro'
                """, {
                    "from": s["station_id"],
                    "to": adj["station_id"],
                    "time": adj["travel_time_min"],
                    "line": adj.get("line", "")
                })

        # ─────────────────────────────────────────────
        # CREATE NATIONAL RAIL CONNECTIONS
        # ─────────────────────────────────────────────

        for s in rail_stations:
            for adj in s.get("adjacent_stations", []):

                session.run("""
                    MATCH (a:Rail {station_id: $from})
                    MATCH (b:Rail {station_id: $to})

                    // Create directed relationship between rail stations
                    MERGE (a)-[r:CONNECTED_TO {from_id: $from, to_id: $to}]->(b)

                    SET r.travel_time_min = $time,
                        r.line_id = $line,
                        r.network = 'rail'
                """, {
                    "from": s["station_id"],
                    "to": adj["station_id"],
                    "time": adj["travel_time_min"],
                    "line": adj.get("line", "")
                })

        # ─────────────────────────────────────────────
        # CREATE INTERCHANGE CONNECTIONS (metro ↔ rail)
        # ─────────────────────────────────────────────

        for s in metro_stations:

            # Only create interchange if station has a rail connection
            if s.get("is_interchange_national_rail") and s.get("interchange_national_rail_station_id"):

                metro_id = s["station_id"]
                rail_id = s["interchange_national_rail_station_id"]

                # Metro → Rail transfer edge
                session.run("""
                    MATCH (a:Metro {station_id: $metro})
                    MATCH (b:Rail {station_id: $rail})

                    MERGE (a)-[r1:INTERCHANGE_TO {from_id: $metro, to_id: $rail}]->(b)

                    // Fixed transfer time (assumption: 5 minutes)
                    SET r1.transfer_time_min = 5,
                        r1.travel_time_min = 5
                """, {
                    "metro": metro_id,
                    "rail": rail_id
                })

                # Rail → Metro transfer edge (bidirectional interchange)
                session.run("""
                    MATCH (a:Rail {station_id: $rail})
                    MATCH (b:Metro {station_id: $metro})

                    MERGE (a)-[r2:INTERCHANGE_TO {from_id: $rail, to_id: $metro}]->(b)

                    SET r2.transfer_time_min = 5,
                        r2.travel_time_min = 5
                """, {
                    "rail": rail_id,
                    "metro": metro_id
                })

    # Close database connection
    driver.close()

    print("\nNeo4j graph seeded successfully.")
    print("   Open http://localhost:7475 to explore the graph.")


if __name__ == "__main__":
    print("Connecting to Neo4j...")
    seed()