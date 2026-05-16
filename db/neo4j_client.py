"""
Neo4j Client — Urban Relationship Graph
Member responsible: Saad

Nodes:   Citizen, ServiceRequest, Department, District, Technician
Edges:   FILED, ASSIGNED_TO, LOCATED_IN, WORKS_FOR, RESOLVED, LIVES_IN, COVERS, COLLABORATES_WITH

Query categories:
  A – Basic (schema understanding)
  B – Intermediate (analytical value)
  C – Advanced (graph-only power: shortest path, impact, gap analysis)
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


def link_request_to_district(request_id, district_id):
    """Create LOCATED_IN relationship between a ServiceRequest and a District."""
    driver = get_driver()
    with driver.session() as s:
        s.run(
            "MATCH (r:ServiceRequest {id: $rid}), (d:District {id: $did}) "
            "MERGE (r)-[:LOCATED_IN]->(d)",
            rid=request_id, did=district_id
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


# ─────────────────────────────────────────────
# CATEGORY A — Basic Queries
# ─────────────────────────────────────────────

def query_department_coverage():
    """A2. Which departments cover which districts (with COLLECT)."""
    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            "MATCH (dept:Department)-[:COVERS]->(dist:District) "
            "RETURN dept.name AS department, "
            "       COLLECT(dist.name) AS districts_covered "
            "ORDER BY dept.name"
        )
        rows = [dict(r) for r in result]
    return rows


def query_citizen_journey(citizen_name):
    """A3. Full interaction chain for a citizen."""
    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            "MATCH (c:Citizen {name: $name})-[:FILED]->(r:ServiceRequest) "
            "       -[:ASSIGNED_TO]->(dept:Department) "
            "OPTIONAL MATCH (t:Technician)-[:RESOLVED]->(r) "
            "RETURN c.name AS citizen, r.category AS category, "
            "       r.status AS status, dept.name AS department, "
            "       t.name AS resolved_by",
            name=citizen_name
        )
        rows = [dict(r) for r in result]
    return rows


# ─────────────────────────────────────────────
# CATEGORY B — Intermediate Queries
# ─────────────────────────────────────────────

def query_district_workload():
    """B3. Districts ranked by open-issue count."""
    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            "MATCH (r:ServiceRequest)-[:LOCATED_IN]->(d:District) "
            "WHERE r.status = 'OPEN' "
            "RETURN d.name AS district, COUNT(r) AS open_issues "
            "ORDER BY open_issues DESC"
        )
        rows = [dict(r) for r in result]
    return rows


def query_department_efficiency():
    """B4. Resolved vs total per department."""
    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            "MATCH (r:ServiceRequest)-[:ASSIGNED_TO]->(dept:Department) "
            "WITH dept, COUNT(r) AS total, "
            "     SUM(CASE WHEN r.status = 'RESOLVED' THEN 1 ELSE 0 END) AS resolved "
            "RETURN dept.name AS department, total, resolved, "
            "       CASE WHEN total > 0 THEN ROUND(100.0 * resolved / total, 1) "
            "            ELSE 0 END AS resolution_rate_pct "
            "ORDER BY resolution_rate_pct DESC"
        )
        rows = [dict(r) for r in result]
    return rows


# ─────────────────────────────────────────────
# CATEGORY C — Advanced / Graph-Only Queries
# ─────────────────────────────────────────────

def query_shortest_path(from_name, to_name):
    """C1. Shortest path between any Citizen and any Department."""
    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            "MATCH (start:Citizen {name: $from_name}), "
            "      (end:Department {name: $to_name}) "
            "MATCH path = shortestPath((start)-[*]-(end)) "
            "UNWIND nodes(path) AS n "
            "RETURN labels(n)[0] AS type, n.name AS name, "
            "       n.id AS id, n.category AS category",
            from_name=from_name, to_name=to_name
        )
        rows = [dict(r) for r in result]
    return rows


def query_impact_analysis(dept_name):
    """C2. If a department goes down, who/what is affected?"""
    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            "MATCH (dept:Department {name: $name}) "
            "OPTIONAL MATCH (dept)<-[:ASSIGNED_TO]-(r:ServiceRequest)<-[:FILED]-(c:Citizen) "
            "OPTIONAL MATCH (dept)-[:COVERS]->(d:District) "
            "RETURN dept.name AS department, "
            "       COLLECT(DISTINCT c.name) AS affected_citizens, "
            "       COLLECT(DISTINCT d.name) AS affected_districts, "
            "       COUNT(DISTINCT r) AS requests_orphaned",
            name=dept_name
        )
        row = result.single()
    return dict(row) if row else {}


def query_collaboration_gaps():
    """C4. Departments that share districts but DON'T yet formally collaborate."""
    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            "MATCH (d1:Department)-[:COVERS]->(dist:District)<-[:COVERS]-(d2:Department) "
            "WHERE d1.id < d2.id "
            "  AND NOT (d1)-[:COLLABORATES_WITH]-(d2) "
            "RETURN d1.name AS dept_a, d2.name AS dept_b, "
            "       COLLECT(dist.name) AS shared_districts, "
            "       COUNT(dist) AS overlap_count "
            "ORDER BY overlap_count DESC"
        )
        rows = [dict(r) for r in result]
    return rows


def query_district_connectivity():
    """C5-alt. District connectivity score based on surrounding entities."""
    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            "MATCH (d:District) "
            "OPTIONAL MATCH (d)<-[:COVERS]-(dept:Department) "
            "OPTIONAL MATCH (d)<-[:LIVES_IN]-(c:Citizen) "
            "OPTIONAL MATCH (d)<-[:LOCATED_IN]-(r:ServiceRequest) "
            "RETURN d.name AS district, "
            "       COUNT(DISTINCT dept) AS departments, "
            "       COUNT(DISTINCT c)    AS citizens, "
            "       COUNT(DISTINCT r)    AS requests, "
            "       COUNT(DISTINCT dept) + COUNT(DISTINCT c) AS connectivity_score "
            "ORDER BY connectivity_score DESC"
        )
        rows = [dict(r) for r in result]
    return rows


def query_variable_length_path(district_name, max_hops=3):
    """C5. All entities within N hops of a district."""
    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            "MATCH path = (d:District {name: $name})-[*1.." + str(int(max_hops)) + "]-(connected) "
            "RETURN DISTINCT labels(connected)[0] AS type, "
            "       connected.name AS name, "
            "       length(path) AS distance "
            "ORDER BY distance, type",
            name=district_name
        )
        rows = [dict(r) for r in result]
    return rows


# ─────────────────────────────────────────────
# VISUAL GRAPH — returns nodes + edges for vis.js
# ─────────────────────────────────────────────

def query_visual_graph(limit=150):
    """Return the full graph as nodes + edges for front-end visualization."""
    driver = get_driver()
    COLOR_MAP = {
        "Citizen":        "#059669",
        "Department":     "#1d4ed8",
        "District":       "#d97706",
        "Technician":     "#7c3aed",
        "ServiceRequest": "#dc2626",
    }
    SHAPE_MAP = {
        "Citizen":        "dot",
        "Department":     "diamond",
        "District":       "triangle",
        "Technician":     "star",
        "ServiceRequest": "square",
    }
    with driver.session() as s:
        result = s.run(
            "MATCH (a)-[r]->(b) "
            "RETURN id(a) AS source_id, labels(a)[0] AS source_label, "
            "       a.name AS source_name, a.id AS source_key, "
            "       a.category AS source_cat, "
            "       type(r) AS rel_type, "
            "       id(b) AS target_id, labels(b)[0] AS target_label, "
            "       b.name AS target_name, b.id AS target_key, "
            "       b.category AS target_cat "
            "LIMIT $limit",
            limit=limit
        )
        nodes = {}
        edges = []
        for row in result:
            for prefix in ("source", "target"):
                nid   = row[f"{prefix}_id"]
                label = row[f"{prefix}_label"]
                name  = row[f"{prefix}_name"] or row[f"{prefix}_cat"] or row[f"{prefix}_key"]
                if nid not in nodes:
                    nodes[nid] = {
                        "id":    nid,
                        "label": name or str(nid),
                        "group": label,
                        "color": COLOR_MAP.get(label, "#888"),
                        "shape": SHAPE_MAP.get(label, "dot"),
                    }
            edges.append({
                "from":  row["source_id"],
                "to":    row["target_id"],
                "label": row["rel_type"],
            })
    return {"nodes": list(nodes.values()), "edges": edges}
