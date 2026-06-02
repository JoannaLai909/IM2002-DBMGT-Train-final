// Deprecated: seeding is now done via skeleton/seed_neo4j.py
// which loads data directly from train-mock-data/ JSON files.
//
// If you prefer Cypher-file seeding, implement your graph schema here.
// Run with: python skeleton/seed_neo4j.py (or via the Neo4j Browser)
// =====================
// CLEAN GRAPH
// =====================
MATCH (n) DETACH DELETE n;


// =====================
// METRO STATIONS
// =====================
UNWIND $metro_stations AS s
CREATE (:Station {
    station_id: s.station_id,
    name: s.name,
    network: "metro",
    lines: s.lines
});


// =====================
// NATIONAL RAIL STATIONS
// =====================
UNWIND $rail_stations AS s
CREATE (:Station {
    station_id: s.station_id,
    name: s.name,
    network: "rail",
    lines: s.lines
});


// =====================
// METRO CONNECTIONS (BIDIRECTIONAL)
// =====================
UNWIND $metro_stations AS s
UNWIND s.adjacent_stations AS a

MATCH (x:Station {station_id: s.station_id})
MATCH (y:Station {station_id: a.station_id})

CREATE (x)-[:CONNECTED_TO {
    travel_time_min: a.travel_time_min,
    line: a.line,
    network: "metro"
}]->(y)

CREATE (y)-[:CONNECTED_TO {
    travel_time_min: a.travel_time_min,
    line: a.line,
    network: "metro"
}]->(x);



// =====================
// RAIL CONNECTIONS (BIDIRECTIONAL)
// =====================
UNWIND $rail_stations AS s
UNWIND s.adjacent_stations AS a

MATCH (x:Station {station_id: s.station_id})
MATCH (y:Station {station_id: a.station_id})

CREATE (x)-[:CONNECTED_TO {
    travel_time_min: a.travel_time_min,
    line: a.line,
    network: "rail"
}]->(y)

CREATE (y)-[:CONNECTED_TO {
    travel_time_min: a.travel_time_min,
    line: a.line,
    network: "rail"
}]->(x);



// =====================
// INTERCHANGE (METRO → RAIL)
// =====================
UNWIND $metro_stations AS m
WITH m
WHERE m.is_interchange_national_rail = true

MATCH (a:Station {station_id: m.station_id})
MATCH (b:Station {station_id: m.interchange_national_rail_station_id})

CREATE (a)-[:INTERCHANGE_TO {
    transfer_time_min: 5
}]->(b)

CREATE (b)-[:INTERCHANGE_TO {
    transfer_time_min: 5
}]->(a);