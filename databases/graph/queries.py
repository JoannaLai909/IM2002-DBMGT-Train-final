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
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def example_count_nodes() -> int:
    """Example: count all nodes currently in the graph."""
    with _driver() as driver:
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) AS total")
            return result.single()["total"]

# ── FASTEST ROUTE (Dijkstra by travel_time_min) ───────────────────────────────

def query_shortest_route(origin_id: str, destination_id: str, network: str = "auto") -> dict:
    """
    Find the fastest path between two stations, minimising total travel time.
    Uses apoc.algo.dijkstra (APOC required; enabled in docker-compose.yml).
    """
    with _driver() as driver:
        with driver.session() as session:
            lbl = "" if network == "auto" else (":Metro" if network == "metro" else ":Rail")
            cypher = f"""
            MATCH (start{lbl} {{station_id: $origin}})
            MATCH (end{lbl} {{station_id: $destination}})
            CALL apoc.algo.dijkstra(start, end, 'CONNECTED_TO|INTERCHANGE_TO', 'travel_time_min') YIELD path, weight
            RETURN weight AS total_time_min,
                   [n IN nodes(path) | {{station_id: n.station_id, name: n.name, line_id: n.line_id}}] AS stations,
                   [r IN relationships(path) | {{type: type(r), time: coalesce(r.travel_time_min, r.transfer_time_min, 0)}}] AS conns
            """
            res = session.run(cypher, {"origin": origin_id, "destination": destination_id}).single()
            if not res:
                return {"found": False, "origin_id": origin_id, "destination_id": destination_id, "total_time_min": 0, "path": [], "legs": []}
            
            s, c = res["stations"], res["conns"]
            legs = [{"from": s[i]["name"], "to": s[i+1]["name"], "type": c[i]["type"], "duration_min": c[i]["time"]} for i in range(len(c))]
            return {"found": True, "origin_id": origin_id, "destination_id": destination_id, "total_time_min": res["total_time_min"], "path": s, "legs": legs}

# ── CHEAPEST ROUTE (Dijkstra by fare) ────────────────────────────────────────

def query_cheapest_route(origin_id: str, destination_id: str, network: str = "auto", fare_class: str = "standard") -> dict:
    """Find the cheapest path between two stations, minimising total estimated fare."""
    with _driver() as driver:
        with driver.session() as session:
            prop = "fare_first" if fare_class == "first" else "fare_standard"
            lbl = "" if network == "auto" else (":Metro" if network == "metro" else ":Rail")
            cypher = f"""
            MATCH (start{lbl} {{station_id: $origin}})
            MATCH (end{lbl} {{station_id: $destination}})
            CALL apoc.algo.dijkstra(start, end, 'CONNECTED_TO|INTERCHANGE_TO', '{prop}') YIELD path, weight
            RETURN weight AS total_fare,
                   [n IN nodes(path) | {{station_id: n.station_id, name: n.name}}] AS stations,
                   [r IN relationships(path) | {{type: type(r), fare: coalesce(r.{prop}, 0)}}] AS conns
            """
            res = session.run(cypher, {"origin": origin_id, "destination": destination_id}).single()
            if not res:
                return {"found": False, "total_fare_usd": 0.0, "stations": [], "legs": []}
            
            s, c = res["stations"], res["conns"]
            legs = [{"from": s[i]["name"], "to": s[i+1]["name"], "type": c[i]["type"], "fare_usd": float(c[i]["fare"])} for i in range(len(c))]
            return {"found": True, "total_fare_usd": float(res["total_fare"]), "stations": s, "legs": legs}

# ── ALTERNATIVE ROUTES (avoiding a station) ───────────────────────────────────

def query_alternative_routes(origin_id: str, destination_id: str, avoid_station_id: str, network: str = "auto", max_routes: int = 3) -> list[list[dict]]:
    """Find paths between two stations that avoid a specific intermediate station."""
    with _driver() as driver:
        with driver.session() as session:
            lbl = "" if network == "auto" else (":Metro" if network == "metro" else ":Rail")
            rel = "CONNECTED_TO|INTERCHANGE_TO" if network == "auto" else "CONNECTED_TO"
            cypher = f"""
            MATCH (start{lbl} {{station_id: $origin}})
            MATCH (end{lbl} {{station_id: $destination}})
            MATCH p = allShortestPaths((start)-[:{rel}*..20]->(end))
            WHERE NONE(n IN nodes(p) WHERE n.station_id = $avoid)
            RETURN [n IN nodes(p) | {{station_id: n.station_id, name: n.name}}] AS stations,
                   [r IN relationships(p) | {{type: type(r), time: coalesce(r.travel_time_min, r.transfer_time_min, 0)}}] AS conns
            LIMIT $limit
            """
            res = session.run(cypher, {"origin": origin_id, "destination": destination_id, "avoid": avoid_station_id, "limit": max_routes})
            routes = []
            for rec in res:
                s, c = rec["stations"], rec["conns"]
                routes.append([{"from": s[i]["name"], "to": s[i+1]["name"], "type": c[i]["type"], "duration_min": c[i]["time"]} for i in range(len(c))])
            return routes

# ── CROSS-NETWORK INTERCHANGE PATH ───────────────────────────────────────────

def query_interchange_path(origin_id: str, destination_id: str) -> dict:
    """Find a path between a metro station and a national rail station via interchanges."""
    with _driver() as driver:
        with driver.session() as session:
            cypher = """
            MATCH (start {station_id: $origin}), (end {station_id: $destination})
            MATCH p = shortestPath((start)-[:CONNECTED_TO|INTERCHANGE_TO*..20]->(end))
            WHERE ANY(r IN relationships(p) WHERE type(r) = 'INTERCHANGE_TO')
            RETURN [n IN nodes(p) | {station_id: n.station_id, name: n.name}] AS stations,
                   [r IN relationships(p) | type(r)] AS conns,
                   reduce(t = 0, r IN relationships(p) | t + coalesce(r.travel_time_min, r.transfer_time_min, 0)) AS total_time
            """
            res = session.run(cypher, {"origin": origin_id, "destination": destination_id}).single()
            if not res:
                return {"found": False, "stations": [], "legs": [], "total_time_min": 0}
            
            s, c = res["stations"], res["conns"]
            legs = []
            
            # Translate raw node hops into explicit human actions (connection vs transfer)
            for i in range(len(c)):
                if c[i] == 'INTERCHANGE_TO':
                    legs.append({
                        "action": f"Transfer inside {s[i]['name']} from Metro ({s[i]['station_id']}) to Rail ({s[i+1]['station_id']})"
                    })
                else:
                    legs.append({
                        "action": f"Take train from {s[i]['name']} ({s[i]['station_id']}) to {s[i+1]['name']} ({s[i+1]['station_id']})"
                    })
                    
            return {
                "found": True, 
                "stations": s, 
                "legs": legs, 
                "total_time_min": res["total_time"]
            }
        
# ── DELAY RIPPLE ANALYSIS ─────────────────────────────────────────────────────

def query_delay_ripple(delayed_station_id: str, hops: int = 2) -> list[dict]:
    """Find all stations within N hops of a delayed or disrupted station."""
    h = max(1, min(hops, 10))
    cypher = f"""
    MATCH (s {{station_id: $id}})
    MATCH p = (s)-[:CONNECTED_TO*1..{h}]-(n)
    WHERE n.station_id <> s.station_id
    RETURN DISTINCT n.station_id AS station_id, n.name AS name, min(length(p)) AS hops_away, collect(DISTINCT n.line_id) AS lines_affected
    ORDER BY hops_away, name
    """
    with _driver() as driver:
        with driver.session() as session:
            res = session.run(cypher, {"id": delayed_station_id})
            return [{"station_id": r["station_id"], "name": r["name"], "hops_away": r["hops_away"], "lines_affected": r["lines_affected"]} for r in res]

# ── STATION CONNECTIONS ───────────────────────────────────────────────────────

def query_station_connections(station_id: str) -> list[dict]:
    """List all direct connections from a given station."""
    cypher = """
    MATCH (s {station_id: $id})-[r:CONNECTED_TO|INTERCHANGE_TO]->(n)
    RETURN n.station_id AS station_id, n.name AS name, type(r) AS connection_type, coalesce(r.travel_time_min, r.transfer_time_min, 0) AS travel_time_min
    ORDER BY name
    """
    with _driver() as driver:
        with driver.session() as session:
            res = session.run(cypher, {"id": station_id})
            return [dict(r) for r in res]