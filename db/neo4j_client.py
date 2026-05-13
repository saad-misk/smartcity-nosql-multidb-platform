"""
Neo4j Client — Urban Relationship Graph
Member responsible: Saad

Nodes:   Citizen, ServiceRequest, Department, District, Technician
Edges:   FILED, ASSIGNED_TO, LOCATED_IN, WORKS_FOR, RESOLVED, LIVES_IN, COVERS, COLLABORATES_WITH
"""

import os
from neo4j import GraphDatabase


def get_driver():
    uri      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
    user     = os.getenv("NEO4J_USER",     "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "smartcity123")
    return GraphDatabase.driver(uri, auth=(user, password))


def init_neo4j():
    """Create constraints and indexes."""
    driver = get_driver()
    with driver.session() as s:
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Citizen)        REQUIRE c.id IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (r:ServiceRequest) REQUIRE r.id IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (d:Department)     REQUIRE d.id IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (d:District)       REQUIRE d.id IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (t:Technician)     REQUIRE t.id IS UNIQUE")
    print("✅ Neo4j constraints created.")


# ─────────────────────────────────────────────
# NODE CREATION
# ─────────────────────────────────────────────

def create_citizen_node(citizen_id, name, district_id):
    driver = get_driver()
    with driver.session() as s:
        s.run(
            "MERGE (c:Citizen {id: $id}) SET c.name=$name "
            "WITH c "
            "MATCH (d:District {id: $district_id}) "
            "MERGE (c)-[:LIVES_IN]->(d)",
            id=citizen_id, name=name, district_id=district_id
        )

def create_request_node(request_id, category, status, citizen_id, dept_id):
    driver = get_driver()
    with driver.session() as s:
        s.run(
            "MERGE (r:ServiceRequest {id: $id}) "
            "SET r.category=$category, r.status=$status "
            "WITH r "
            "MATCH (c:Citizen {id: $citizen_id}) "
            "MERGE (c)-[:FILED]->(r) "
            "WITH r "
            "MATCH (d:Department {id: $dept_id}) "
            "MERGE (r)-[:ASSIGNED_TO]->(d)",
            id=request_id, category=category, status=status,
            citizen_id=citizen_id, dept_id=dept_id
        )

def mark_request_resolved(request_id, tech_id):
    driver = get_driver()
    with driver.session() as s:
        s.run(
            "MATCH (r:ServiceRequest {id: $req_id}) "
            "SET r.status='RESOLVED' "
            "WITH r "
            "MATCH (t:Technician {id: $tech_id}) "
            "MERGE (t)-[:RESOLVED]->(r)",
            req_id=request_id, tech_id=tech_id
        )

# ─────────────────────────────────────────────
# SEED STATIC NODES (Departments & Districts)
# ─────────────────────────────────────────────

DEPARTMENTS = [
    {"id": "dept_public_works",  "name": "Public Works"},
    {"id": "dept_traffic",       "name": "Traffic Authority"},
    {"id": "dept_sanitation",    "name": "Sanitation"},
    {"id": "dept_lighting",      "name": "Street Lighting"},
    {"id": "dept_emergency",     "name": "Emergency Services"},
    {"id": "dept_utilities",     "name": "Water & Utilities"},
]

DISTRICTS = [
    {"id": "dist_1", "name": "Old City"},
    {"id": "dist_2", "name": "Commercial Center"},
    {"id": "dist_3", "name": "University Zone"},
    {"id": "dist_4", "name": "Northern Suburbs"},
    {"id": "dist_5", "name": "Industrial Area"},
    {"id": "dist_6", "name": "Residential East"},
    {"id": "dist_7", "name": "Residential West"},
    {"id": "dist_8", "name": "Southern Zone"},
]

# Which departments cover which districts
DEPT_DISTRICT_COVERAGE = [
    ("dept_sanitation",   ["dist_1","dist_2","dist_3","dist_4"]),
    ("dept_lighting",     ["dist_1","dist_2","dist_5","dist_6"]),
    ("dept_traffic",      ["dist_2","dist_3","dist_4","dist_7"]),
    ("dept_public_works", ["dist_5","dist_6","dist_7","dist_8"]),
    ("dept_utilities",    ["dist_1","dist_3","dist_5","dist_8"]),
    ("dept_emergency",    ["dist_1","dist_2","dist_3","dist_4","dist_5","dist_6","dist_7","dist_8"]),
]

DEPT_COLLABORATIONS = [
    ("dept_sanitation",   "dept_public_works"),
    ("dept_lighting",     "dept_traffic"),
    ("dept_emergency",    "dept_utilities"),
]

TECHNICIANS = [
    {"id": "tech_1", "name": "Khaled Hassan",  "dept": "dept_lighting"},
    {"id": "tech_2", "name": "Omar Nasser",    "dept": "dept_sanitation"},
    {"id": "tech_3", "name": "Yusuf Kareem",   "dept": "dept_traffic"},
    {"id": "tech_4", "name": "Bilal Mansour",  "dept": "dept_public_works"},
    {"id": "tech_5", "name": "Tariq Saleh",    "dept": "dept_utilities"},
]


def seed_static_nodes():
    driver = get_driver()
    with driver.session() as s:
        for dept in DEPARTMENTS:
            s.run("MERGE (d:Department {id: $id}) SET d.name=$name", **dept)

        for dist in DISTRICTS:
            s.run("MERGE (d:District {id: $id}) SET d.name=$name", **dist)

        for dept_id, dist_ids in DEPT_DISTRICT_COVERAGE:
            for dist_id in dist_ids:
                s.run(
                    "MATCH (dept:Department {id:$dept_id}), (dist:District {id:$dist_id}) "
                    "MERGE (dept)-[:COVERS]->(dist)",
                    dept_id=dept_id, dist_id=dist_id
                )

        for d1, d2 in DEPT_COLLABORATIONS:
            s.run(
                "MATCH (a:Department {id:$d1}), (b:Department {id:$d2}) "
                "MERGE (a)-[:COLLABORATES_WITH]->(b)",
                d1=d1, d2=d2
            )

        for tech in TECHNICIANS:
            s.run(
                "MERGE (t:Technician {id:$id}) SET t.name=$name "
                "WITH t MATCH (d:Department {id:$dept}) "
                "MERGE (t)-[:WORKS_FOR]->(d)",
                id=tech["id"], name=tech["name"], dept=tech["dept"]
            )
    print("✅ Neo4j static nodes seeded.")


# ─────────────────────────────────────────────
# GRAPH QUERIES (Cypher)
# ─────────────────────────────────────────────

def query_citizen_requests(citizen_id):
    """All requests filed by a citizen."""
    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            "MATCH (c:Citizen {id:$cid})-[:FILED]->(r:ServiceRequest) "
            "RETURN r.id AS request_id, r.category AS category, r.status AS status",
            cid=citizen_id
        )
        rows = [dict(r) for r in result]
    return rows


def query_dept_technicians(dept_id):
    """Technicians working for a department and their resolved request counts."""
    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            "MATCH (t:Technician)-[:WORKS_FOR]->(d:Department {id:$dept_id}) "
            "OPTIONAL MATCH (t)-[:RESOLVED]->(r:ServiceRequest) "
            "RETURN t.name AS technician, COUNT(r) AS resolved_count "
            "ORDER BY resolved_count DESC",
            dept_id=dept_id
        )
        rows = [dict(r) for r in result]
    return rows


def query_cross_district_reporters():
    """Citizens who reported issues outside their home district."""
    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            "MATCH (c:Citizen)-[:FILED]->(r:ServiceRequest)-[:LOCATED_IN]->(d:District) "
            "WHERE NOT (c)-[:LIVES_IN]->(d) "
            "RETURN c.name AS citizen, d.name AS reported_in_district "
            "LIMIT 20"
        )
        rows = [dict(r) for r in result]
    return rows


def query_shared_district_departments():
    """Departments that share coverage over the same district."""
    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            "MATCH (d1:Department)-[:COVERS]->(dist:District)<-[:COVERS]-(d2:Department) "
            "WHERE d1.id < d2.id "
            "RETURN d1.name AS dept_a, d2.name AS dept_b, dist.name AS shared_district "
            "ORDER BY dist.name"
        )
        rows = [dict(r) for r in result]
    return rows


def query_top_technicians(limit=5):
    """Technicians ranked by number of resolved requests."""
    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            "MATCH (t:Technician)-[:RESOLVED]->(r:ServiceRequest) "
            "RETURN t.name AS technician, COUNT(r) AS resolved "
            "ORDER BY resolved DESC LIMIT $limit",
            limit=limit
        )
        rows = [dict(r) for r in result]
    return rows


def query_graph_stats():
    """Quick node counts for the dashboard."""
    driver = get_driver()
    with driver.session() as s:
        nodes = s.run(
            "MATCH (n) RETURN labels(n)[0] AS label, COUNT(n) AS count"
        )
        rels = s.run("MATCH ()-[r]->() RETURN COUNT(r) AS total")
        node_counts = {r["label"]: r["count"] for r in nodes}
        rel_count   = rels.single()["total"]
    return {"nodes": node_counts, "relationships": rel_count}
