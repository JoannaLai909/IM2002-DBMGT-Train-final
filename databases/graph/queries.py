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
    return GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD)
    )


# ─────────────────────────────
# FASTEST ROUTE
# ─────────────────────────────
def query_shortest_route(origin_id: str, destination_id: str, network: str = "auto") -> dict:

    with _driver() as driver:
        with driver.session() as session:

            result = session.run("""
            MATCH (start:Station {station_id: $origin})
            MATCH (end:Station {station_id: $destination})

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
                "origin": origin_id,
                "destination": destination_id
            })

            record = result.single()

            if not record:
                return {
                    "found": False,
                    "origin_id": origin_id,
                    "destination_id": destination_id,
                    "total_time_min": 0,
                    "path": []
                }

            return {
                "found": True,
                "origin_id": origin_id,
                "destination_id": destination_id,
                "total_time_min": record["total_time_min"],
                "path": record["path"]
            }


# ─────────────────────────────
# CHEAPEST ROUTE
# ─────────────────────────────
def query_cheapest_route(*args, **kwargs):
    return {
        "found": False,
        "note": "Handled in PostgreSQL layer"
    }


# ─────────────────────────────
# ALTERNATIVE ROUTES
# ─────────────────────────────
def query_alternative_routes(
    origin_id: str,
    destination_id: str,
    avoid_station_id: str,
    max_routes: int = 3
) -> list[list[dict]]:

    with _driver() as driver:
        with driver.session() as session:

            result = session.run("""
            MATCH (start:Station {station_id: $origin})
            MATCH (end:Station {station_id: $destination})

            MATCH p = allShortestPaths(
                (start)-[:CONNECTED_TO*..8]->(end)
            )
            WHERE NONE(n IN nodes(p) WHERE n.station_id = $avoid)

            RETURN p
            LIMIT $limit
            """, {
                "origin": origin_id,
                "destination": destination_id,
                "avoid": avoid_station_id,
                "limit": max_routes
            })

            routes = []

            for r in result:
                p = r["p"]
                routes.append([
                    {"station_id": n["station_id"], "name": n["name"]}
                    for n in p.nodes
                ])

            return routes


# ─────────────────────────────
# INTERCHANGE PATH
# ─────────────────────────────
def query_interchange_path(origin_id: str, destination_id: str) -> dict:

    with _driver() as driver:
        with driver.session() as session:

            result = session.run("""
            MATCH (start:Station {station_id: $origin})
            MATCH (end:Station {station_id: $destination})

            MATCH p = shortestPath(
                (start)-[:CONNECTED_TO|INTERCHANGE_TO*..20]->(end)
            )

            RETURN p
            """, {
                "origin": origin_id,
                "destination": destination_id
            })

            record = result.single()

            if not record:
                return {"found": False, "stations": []}

            path = record["p"]

            return {
                "found": True,
                "stations": [
                    {"station_id": n["station_id"], "name": n["name"]}
                    for n in path.nodes
                ]
            }


# ─────────────────────────────
# DELAY RIPPLE
# ─────────────────────────────
def query_delay_ripple(delayed_station_id: str, hops: int = 2):

    with _driver() as driver:
        with driver.session() as session:

            result = session.run("""
            MATCH (s:Station {station_id: $id})
            MATCH path = (s)-[:CONNECTED_TO*1..$hops]-(n)
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


# ─────────────────────────────
# STATION CONNECTIONS
# ─────────────────────────────
def query_station_connections(station_id: str):

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