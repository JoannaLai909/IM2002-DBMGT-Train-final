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


# Create Neo4j driver connection
def _driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


# ─────────────────────────────────────────────
# FASTEST ROUTE
# ─────────────────────────────────────────────

def query_shortest_route(origin_id: str, destination_id: str, network: str = "auto") -> dict:
    """Find the fastest route between two stations using Dijkstra's algorithm."""
    
    with _driver() as driver:
        with driver.session() as session:
            
            # If network is auto, allow cross-network routing (metro + rail)
            if network == "auto":
                cypher = """
                MATCH (start:Station {station_id: $origin})
                MATCH (end:Station {station_id: $destination})
                
                # Run APOC Dijkstra using travel_time_min as weight
                CALL apoc.algo.dijkstra(
                    start, end, 'CONNECTED_TO|INTERCHANGE_TO', 'travel_time_min'
                ) YIELD path, weight
                
                RETURN weight AS total_time_min,
                       [n IN nodes(path) | {station_id: n.station_id, name: n.name}] AS path
                """
            else:
                # Restrict routing within same network only
                cypher = """
                MATCH (start:Station {station_id: $origin, network: $network})
                MATCH (end:Station {station_id: $destination, network: $network})
                
                CALL apoc.algo.dijkstra(
                    start, end, 'CONNECTED_TO', 'travel_time_min'
                ) YIELD path, weight
                
                RETURN weight AS total_time_min,
                       [n IN nodes(path) | {station_id: n.station_id, name: n.name}] AS path
                """
            
            # Execute Cypher query
            result = session.run(cypher, {
                "origin": origin_id,
                "destination": destination_id,
                "network": network
            })
            
            record = result.single()
            
            # If no route found
            if not record:
                return {
                    "found": False,
                    "origin_id": origin_id,
                    "destination_id": destination_id,
                    "total_hops": 0,
                    "path": []
                }
            
            return {
                "found": True,
                "origin_id": origin_id,
                "destination_id": destination_id,
                "total_time_min": record["total_time_min"],
                "total_hops": len(record["path"]),
                "path": record["path"]
            }


# ─────────────────────────────
# CHEAPEST ROUTE
# ─────────────────────────────

def query_cheapest_route(origin_id: str, destination_id: str, network: str = "auto", fare_class: str = "standard") -> dict:
    # Not implemented yet (requires pricing model or GDS)
    return {
        "found": False,
        "note": "Cheapest route not implemented (requires GDS or pricing model)"
    }


# ─────────────────────────────────────────────
# ALTERNATIVE ROUTES
# ─────────────────────────────────────────────

def query_alternative_routes(origin_id: str, destination_id: str, avoid_station_id: str, network: str = "auto", max_routes: int = 3) -> list[list[dict]]:
    """Find alternative routes avoiding a specific station."""
    
    with _driver() as driver:
        with driver.session() as session:
            
            if network == "auto":
                cypher = """
                MATCH (start:Station {station_id: $origin})
                MATCH (end:Station {station_id: $destination})
                
                # Find all shortest paths between two stations
                MATCH p = allShortestPaths(
                    (start)-[:CONNECTED_TO|INTERCHANGE_TO*..15]->(end)
                )
                
                # Exclude paths that contain avoided station
                WHERE NONE(n IN nodes(p) WHERE n.station_id = $avoid)
                
                RETURN p
                LIMIT $limit
                """
            else:
                cypher = f"""
                MATCH (start:Station {{station_id: $origin, network: '{network}'}})
                MATCH (end:Station {{station_id: $destination, network: '{network}'}})
                
                MATCH p = allShortestPaths(
                    (start)-[:CONNECTED_TO*..15]->(end)
                )
                
                WHERE NONE(n IN nodes(p) WHERE n.station_id = $avoid)
                
                RETURN p
                LIMIT $limit
                """
            
            result = session.run(cypher, {
                "origin": origin_id,
                "destination": destination_id,
                "avoid": avoid_station_id,
                "limit": max_routes
            })

            routes = []
            
            # Convert Neo4j path objects into Python dictionaries
            for record in result:
                p = record["p"]
                routes.append([
                    {"station_id": n["station_id"], "name": n["name"]}
                    for n in p.nodes
                ])

            return routes


# ─────────────────────────────────────────────
# INTERCHANGE PATH
# ─────────────────────────────────────────────

def query_interchange_path(origin_id: str, destination_id: str) -> dict:
    """Find a path that may span both metro and rail networks."""
    
    with _driver() as driver:
        with driver.session() as session:

            result = session.run("""
            MATCH (start:Station {station_id: $origin})
            MATCH (end:Station {station_id: $destination})

            # Find shortest path including transfer edges
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


# ─────────────────────────────────────────────
# DELAY RIPPLE
# ─────────────────────────────────────────────

def query_delay_ripple(delayed_station_id: str, hops: int = 2) -> list[dict]:
    """Find all stations affected by a delay within N hops."""

    # Clamp hops to avoid excessive graph traversal
    hops = max(1, min(hops, 10))

    cypher = f"""
    MATCH (s:Station {{station_id: $id}})
    
    # Traverse up to N hops from delayed station
    MATCH p = (s)-[:CONNECTED_TO*1..{hops}]-(n)

    WHERE n.station_id <> s.station_id
      AND n.network = s.network

    RETURN DISTINCT
           n.station_id AS station_id,
           n.name AS name,
           min(length(p)) AS hops_away

    ORDER BY hops_away, name
    """

    with _driver() as driver:
        with driver.session() as session:

            result = session.run(
                cypher,
                {"id": delayed_station_id}
            )

            return [
                {
                    "station_id": record["station_id"],
                    "name": record["name"],
                    "hops_away": record["hops_away"]
                }
                for record in result
            ]


# ─────────────────────────────────────────────
# STATION CONNECTIONS
# ─────────────────────────────────────────────

def query_station_connections(station_id: str) -> list[dict]:
    """Get all directly connected stations from a given station."""

    with _driver() as driver:
        with driver.session() as session:

            result = session.run("""
            MATCH (s:Station {station_id: $id})
                  -[r:CONNECTED_TO|INTERCHANGE_TO]->
                  (n)

            RETURN
                n.station_id AS station_id,
                n.name AS name,
                type(r) AS connection_type,
                coalesce(
                    r.travel_time_min,
                    r.transfer_time_min
                ) AS travel_time_min

            ORDER BY name
            """, {
                "id": station_id
            })

            return [
                {
                    "station_id": record["station_id"],
                    "name": record["name"],
                    "connection_type": record["connection_type"],
                    "travel_time_min": record["travel_time_min"]
                }
                for record in result
            ]