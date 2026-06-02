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

sys.path.insert(0, ".")

from neo4j import GraphDatabase
from skeleton.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

_DATA_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "train-mock-data")
)


def _load(filename):
    with open(os.path.join(_DATA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


def seed():
    metro_stations = _load("metro_stations.json")
    rail_stations  = _load("national_rail_stations.json")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:

        # ─────────────────────────────
        # CLEAN GRAPH
        # ─────────────────────────────
        session.run("MATCH (n) DETACH DELETE n")
        print("  Cleared existing graph data")

        # ─────────────────────────────
        # CREATE METRO STATIONS
        # ─────────────────────────────
        for s in metro_stations:
            session.run("""
                CREATE (:Station {
                    station_id: $id,
                    name: $name,
                    network: "metro",
                    lines: $lines
                })
            """, {
                "id": s["station_id"],
                "name": s["name"],
                "lines": s.get("lines", [])
            })

        # ─────────────────────────────
        # CREATE RAIL STATIONS
        # ─────────────────────────────
        for s in rail_stations:
            session.run("""
                CREATE (:Station {
                    station_id: $id,
                    name: $name,
                    network: "rail",
                    lines: $lines
                })
            """, {
                "id": s["station_id"],
                "name": s["name"],
                "lines": s.get("lines", [])
            })

        # ─────────────────────────────
        # CREATE METRO CONNECTED_TO EDGES
        # ─────────────────────────────
        for s in metro_stations:
            for adj in s.get("adjacent_stations", []):
                session.run("""
                    MATCH (a:Station {station_id: $from})
                    MATCH (b:Station {station_id: $to})
                    CREATE (a)-[:CONNECTED_TO {
                        travel_time_min: $time,
                        line: $line,
                        network: "metro"
                    }]->(b)
                """, {
                    "from": s["station_id"],
                    "to": adj["station_id"],
                    "time": adj["travel_time_min"],
                    "line": adj.get("line", "")
                })

        # ─────────────────────────────
        # CREATE RAIL CONNECTED_TO EDGES
        # ─────────────────────────────
        for s in rail_stations:
            for adj in s.get("adjacent_stations", []):
                session.run("""
                    MATCH (a:Station {station_id: $from})
                    MATCH (b:Station {station_id: $to})
                    CREATE (a)-[:CONNECTED_TO {
                        travel_time_min: $time,
                        line: $line,
                        network: "rail"
                    }]->(b)
                """, {
                    "from": s["station_id"],
                    "to": adj["station_id"],
                    "time": adj["travel_time_min"],
                    "line": adj.get("line", "")
                })

        # ─────────────────────────────
        # CREATE INTERCHANGE EDGES
        # ─────────────────────────────
        for s in metro_stations:
            if s.get("is_interchange_national_rail") and s.get("interchange_national_rail_station_id"):
                session.run("""
                    MATCH (a:Station {station_id: $metro})
                    MATCH (b:Station {station_id: $rail})
                    CREATE (a)-[:INTERCHANGE_TO {
                        transfer_time_min: 5
                    }]->(b)
                    CREATE (b)-[:INTERCHANGE_TO {
                        transfer_time_min: 5
                    }]->(a)
                """, {
                    "metro": s["station_id"],
                    "rail": s["interchange_national_rail_station_id"]
                })

    driver.close()
    print("\nNeo4j graph seeded successfully.")
    print("   Open http://localhost:7475 to explore the graph.")


if __name__ == "__main__":
    print("Connecting to Neo4j...")
    seed()
