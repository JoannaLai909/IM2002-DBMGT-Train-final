"""
TransitFlow — Neo4j Graph Database Layer
=========================================
This module handles all queries to Neo4j.

GRAPH ROLE:
  - Model the dual transit network (city metro M1–M4 + national rail NR1–NR2)
  - Find fastest routes (Dijkstra by travel_time_min via APOC)
  - Find cheapest routes (Dijkstra by fare via APOC)
  - Find alternative routes avoiding a given station
  - Find cross-network interchange paths (metro → rail or rail → metro)
  - Show delay ripple: which stations are affected within N hops

STUDENT TASK
------------
Design your graph schema (node labels, relationship types, properties)
based on the data in train-mock-data/, seed it with skeleton/seed_neo4j.py,
then implement the query_ functions below.

Functions prefixed with `query_` are called by the agent (skeleton/agent.py).
"""

from __future__ import annotations

from typing import Optional

from neo4j import GraphDatabase

from skeleton.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


def _driver():
    """Return a Neo4j driver. Caller is responsible for closing."""
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


# ── Example ───────────────────────────────────────────────────────────────────
# The block below shows the query pattern: open a session, run Cypher, return data.

def example_count_nodes() -> int:
    """Example: count all nodes currently in the graph."""
    with _driver() as driver:
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) AS total")
            return result.single()["total"]

# TODO: Implement the query_ functions below.
# ─────────────────────────────────────────────────────────────────────────────


# ── FASTEST ROUTE (Dijkstra by travel_time_min) ───────────────────────────────

def query_shortest_route(
    origin_id: str,
    destination_id: str,
    network: str = "auto",
) -> dict:

    with _driver() as driver:
        with driver.session() as session:

            result = session.run("""
            MATCH (start:Station {station_id: $origin_id})
            MATCH (end:Station {station_id: $destination_id})

            CALL apoc.algo.dijkstra(
                start,
                end,
                'CONNECTED_TO',
                'travel_time_min'
            ) YIELD path, weight

            RETURN
                weight AS total_time_min,
                [n IN nodes(path) | {
                    station_id: n.station_id,
                    name: n.name
                }] AS path
            """, {
                "origin_id": origin_id,
                "destination_id": destination_id
            })

            record = result.single()

            if not record:
                return {
                    "found": False,
                    "origin_id": origin_id,
                    "destination_id": destination_id,
                    "total_time_min": 0,
                    "path": [],
                    "legs": []
                }

            return {
                "found": True,
                "origin_id": origin_id,
                "destination_id": destination_id,
                "total_time_min": record["total_time_min"],
                "path": record["path"],
                "legs": record["path"]
            }


# ── CHEAPEST ROUTE (Dijkstra by fare) ────────────────────────────────────────

def query_cheapest_route(
    origin_id: str,
    destination_id: str,
    network: str = "auto",
    fare_class: str = "standard",
) -> dict:

    # ⚠️ 不在 graph 做（你的 schema 沒 fare edge）
    return {
        "found": False,
        "note": "Cheapest route handled in PostgreSQL layer"
    }


# ── ALTERNATIVE ROUTES (avoiding a station) ───────────────────────────────────

def query_alternative_routes(
    origin_id: str,
    destination_id: str,
    avoid_station_id: str,
    network: str = "auto",
    max_routes: int = 3,
) -> list[list[dict]]:

    with _driver() as driver:
        with driver.session() as session:

            result = session.run("""
            MATCH (start:Station {station_id: $origin_id})
            MATCH (end:Station {station_id: $destination_id})

            MATCH p = allShortestPaths(
                (start)-[:CONNECTED_TO*..10]->(end)
            )
            WHERE NONE(n IN nodes(p) WHERE n.station_id = $avoid)

            RETURN p
            LIMIT $limit
            """, {
                "origin_id": origin_id,
                "destination_id": destination_id,
                "avoid": avoid_station_id,
                "limit": max_routes
            })

            routes = []

            for r in result:
                path = r["p"]
                routes.append([
                    {"station_id": n["station_id"], "name": n["name"]}
                    for n in path.nodes
                ])

            return routes


# ── CROSS-NETWORK INTERCHANGE PATH ───────────────────────────────────────────

def query_interchange_path(origin_id: str, destination_id: str) -> dict:

    with _driver() as driver:
        with driver.session() as session:

            result = session.run("""
            MATCH (start:Station {station_id: $origin_id})
            MATCH (end:Station {station_id: $destination_id})

            MATCH p = shortestPath(
                (start)-[:CONNECTED_TO|INTERCHANGE_TO*..20]->(end)
            )

            RETURN p
            """, {
                "origin_id": origin_id,
                "destination_id": destination_id
            })

            record = result.single()

            if not record:
                return {
                    "found": False,
                    "stations": [],
                    "interchanges": [],
                    "total_time_min": 0
                }

            path = record["p"]

            nodes = list(path.nodes)
            rels = list(path.relationships)

            stations = [
                {"station_id": n["station_id"], "name": n["name"]}
                for n in nodes
            ]

            interchanges = [
                {
                    "from": r.start_node["station_id"],
                    "to": r.end_node["station_id"]
                }
                for r in rels if r.type == "INTERCHANGE_TO"
            ]

            return {
                "found": True,
                "stations": stations,
                "interchanges": interchanges,
                "total_time_min": len(rels)
            }


# ── DELAY RIPPLE ANALYSIS ─────────────────────────────────────────────────────

def query_delay_ripple(delayed_station_id: str, hops: int = 2) -> list[dict]:

    with _driver() as driver:
        with driver.session() as session:

            result = session.run("""
            MATCH (s:Station {station_id: $id})
            MATCH (s)-[:CONNECTED_TO*1..$hops]-(n)

            RETURN DISTINCT n, length(path) AS hops_away
            """, {
                "id": delayed_station_id,
                "hops": hops
            })

            return [
                {
                    "station_id": r["n"]["station_id"],
                    "name": r["n"]["name"],
                    "hops_away": r["hops_away"]
                }
                for r in result
            ]


# ── STATION CONNECTIONS ───────────────────────────────────────────────────────

def query_station_connections(station_id: str) -> list[dict]:

    with _driver() as driver:
        with driver.session() as session:

            result = session.run("""
            MATCH (s:Station {station_id: $id})-[:CONNECTED_TO]->(n)
            RETURN n
            """, {
                "id": station_id
            })

            return [
                {
                    "station_id": r["n"]["station_id"],
                    "name": r["n"]["name"]
                }
                for r in result
            ]