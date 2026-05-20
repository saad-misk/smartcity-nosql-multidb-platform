"""
Neo4j Client — SmartCity Urban Relationship Graph

Nodes:  Citizen, ServiceRequest, Department, Area, Technician
Edges:  FILED, ASSIGNED_TO, LOCATED_IN, WORKS_FOR, RESOLVED, LIVES_IN, COVERS, COLLABORATES_WITH

Queries are grouped by complexity:
  Basic        — understand the schema, simple lookups
  Intermediate — cross-node analytics
  Advanced     — graph-only power (shortest path, impact, gap detection)
"""

import os
from neo4j import GraphDatabase


def get_driver():
    return GraphDatabase.driver(
        os.getenv("NEO4J_URI",      "bolt://localhost:7687"),
        auth=(
            os.getenv("NEO4J_USER",     "neo4j"),
            os.getenv("NEO4J_PASSWORD", "smartcity123"),
        ),
    )


def init_constraints():
    driver = get_driver()
    with driver.session() as s:
        for label in ["Citizen", "ServiceRequest", "Department", "Area", "Technician"]:
            s.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE")
    print("Neo4j constraints ready.")


# ── Static seed data ──────────────────────────────────────────────────────────

DEPARTMENTS = [
    {"id": "dept_public_works", "name": "Public Works"},
    {"id": "dept_traffic",      "name": "Traffic Authority"},
    {"id": "dept_sanitation",   "name": "Sanitation"},
    {"id": "dept_lighting",     "name": "Street Lighting"},
    {"id": "dept_emergency",    "name": "Emergency Services"},
    {"id": "dept_utilities",    "name": "Water & Utilities"},
]

AREAS = [
    {"id": "dist_1", "name": "Old City"},
    {"id": "dist_2", "name": "Commercial Center"},
    {"id": "dist_3", "name": "University Zone"},
    {"id": "dist_4", "name": "Northern Suburbs"},
    {"id": "dist_5", "name": "Industrial Area"},
    {"id": "dist_6", "name": "Residential East"},
    {"id": "dist_7", "name": "Residential West"},
    {"id": "dist_8", "name": "Southern Zone"},
]

DEPT_AREA_COVERAGE = [
    ("dept_sanitation",   ["dist_1", "dist_2", "dist_3", "dist_4"]),
    ("dept_lighting",     ["dist_1", "dist_2", "dist_5", "dist_6"]),
    ("dept_traffic",      ["dist_2", "dist_3", "dist_4", "dist_7"]),
    ("dept_public_works", ["dist_5", "dist_6", "dist_7", "dist_8"]),
    ("dept_utilities",    ["dist_1", "dist_3", "dist_5", "dist_8"]),
    ("dept_emergency",    ["dist_1", "dist_2", "dist_3", "dist_4",
                           "dist_5", "dist_6", "dist_7", "dist_8"]),
]

COLLABORATIONS = [
    ("dept_sanitation",  "dept_public_works"),
    ("dept_lighting",    "dept_traffic"),
    ("dept_emergency",   "dept_utilities"),
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
        for d in DEPARTMENTS:
            s.run("MERGE (d:Department {id:$id}) SET d.name=$name", **d)
        for a in AREAS:
            s.run("MERGE (a:Area {id:$id}) SET a.name=$name", **a)
        for dept_id, area_ids in DEPT_AREA_COVERAGE:
            for area_id in area_ids:
                s.run(
                    "MATCH (d:Department {id:$dept_id}), (a:Area {id:$area_id}) "
                    "MERGE (d)-[:COVERS]->(a)",
                    dept_id=dept_id, area_id=area_id,
                )
        for d1, d2 in COLLABORATIONS:
            s.run(
                "MATCH (a:Department {id:$d1}), (b:Department {id:$d2}) "
                "MERGE (a)-[:COLLABORATES_WITH]->(b)",
                d1=d1, d2=d2,
            )
        for t in TECHNICIANS:
            s.run(
                "MERGE (t:Technician {id:$id}) SET t.name=$name "
                "WITH t MATCH (d:Department {id:$dept}) "
                "MERGE (t)-[:WORKS_FOR]->(d)",
                id=t["id"], name=t["name"], dept=t["dept"],
            )
    print("Neo4j static nodes seeded.")


# ── Node creation (called when data enters the system) ───────────────────────

def create_citizen_node(citizen_id, name, area_id):
    with get_driver().session() as s:
        s.run(
            "MERGE (c:Citizen {id:$id}) SET c.name=$name "
            "WITH c MATCH (a:Area {id:$area_id}) "
            "MERGE (c)-[:LIVES_IN]->(a)",
            id=citizen_id, name=name, area_id=area_id,
        )


def create_request_node(request_id, category, citizen_id, dept_id):
    with get_driver().session() as s:
        s.run(
            "MERGE (r:ServiceRequest {id:$id}) "
            "SET r.category=$category, r.status='pending' "
            "WITH r "
            "MATCH (c:Citizen {id:$cid}) MERGE (c)-[:FILED]->(r) "
            "WITH r "
            "MATCH (d:Department {id:$did}) MERGE (r)-[:ASSIGNED_TO]->(d)",
            id=request_id, category=category, cid=citizen_id, did=dept_id,
        )


def link_request_to_area(request_id, area_id):
    with get_driver().session() as s:
        s.run(
            "MATCH (r:ServiceRequest {id:$rid}), (a:Area {id:$aid}) "
            "MERGE (r)-[:LOCATED_IN]->(a)",
            rid=request_id, aid=area_id,
        )


def mark_request_resolved(request_id, tech_id):
    with get_driver().session() as s:
        s.run(
            "MATCH (r:ServiceRequest {id:$rid}) SET r.status='resolved' "
            "WITH r MATCH (t:Technician {id:$tid}) "
            "MERGE (t)-[:RESOLVED]->(r)",
            rid=request_id, tid=tech_id,
        )


# ── Basic queries ─────────────────────────────────────────────────────────────

def query_graph_stats():
    """Node and relationship counts for the dashboard."""
    with get_driver().session() as s:
        nodes = {r["label"]: r["count"] for r in
                 s.run("MATCH (n) RETURN labels(n)[0] AS label, COUNT(n) AS count")}
        rels  = s.run("MATCH ()-[r]->() RETURN COUNT(r) AS total").single()["total"]
    return {"nodes": nodes, "relationships": rels}


def query_department_coverage():
    """Which areas each department covers."""
    with get_driver().session() as s:
        result = s.run(
            "MATCH (d:Department)-[:COVERS]->(a:Area) "
            "RETURN d.name AS department, COLLECT(a.name) AS areas "
            "ORDER BY d.name"
        )
        return [dict(r) for r in result]


def query_citizen_requests(citizen_id):
    """All requests filed by a citizen."""
    with get_driver().session() as s:
        result = s.run(
            "MATCH (c:Citizen {id:$cid})-[:FILED]->(r:ServiceRequest) "
            "RETURN r.id AS request_id, r.category AS category, r.status AS status",
            cid=citizen_id,
        )
        return [dict(r) for r in result]


# ── Intermediate queries ──────────────────────────────────────────────────────

def query_area_workload():
    """Areas ranked by number of open (pending) requests."""
    with get_driver().session() as s:
        result = s.run(
            "MATCH (r:ServiceRequest)-[:LOCATED_IN]->(a:Area) "
            "WHERE r.status = 'pending' "
            "RETURN a.name AS area, COUNT(r) AS open_issues "
            "ORDER BY open_issues DESC"
        )
        return [dict(r) for r in result]


def query_department_efficiency():
    """Resolved vs total requests per department with resolution rate."""
    with get_driver().session() as s:
        result = s.run(
            "MATCH (r:ServiceRequest)-[:ASSIGNED_TO]->(d:Department) "
            "WITH d, COUNT(r) AS total, "
            "     SUM(CASE WHEN r.status='resolved' THEN 1 ELSE 0 END) AS resolved "
            "RETURN d.name AS department, total, resolved, "
            "       ROUND(100.0 * resolved / total, 1) AS resolution_rate_pct "
            "ORDER BY resolution_rate_pct DESC"
        )
        return [dict(r) for r in result]


def query_top_technicians(limit=5):
    """Technicians ranked by resolved request count."""
    with get_driver().session() as s:
        result = s.run(
            "MATCH (t:Technician)-[:RESOLVED]->(r:ServiceRequest) "
            "RETURN t.name AS technician, COUNT(r) AS resolved "
            "ORDER BY resolved DESC LIMIT $limit",
            limit=limit,
        )
        return [dict(r) for r in result]


# ── Advanced / graph-only queries ─────────────────────────────────────────────

def query_shortest_path(from_citizen_name, to_dept_name):
    """Shortest connection path between a citizen and a department."""
    with get_driver().session() as s:
        result = s.run(
            "MATCH (start:Citizen {name:$from}), (end:Department {name:$to}) "
            "MATCH path = shortestPath((start)-[*]-(end)) "
            "UNWIND nodes(path) AS n "
            "RETURN labels(n)[0] AS type, n.name AS name, n.id AS id",
            **{"from": from_citizen_name, "to": to_dept_name},
        )
        return [dict(r) for r in result]


def query_impact_analysis(dept_name):
    """If a department goes offline: affected citizens, areas, and request count."""
    with get_driver().session() as s:
        row = s.run(
            "MATCH (d:Department {name:$name}) "
            "OPTIONAL MATCH (d)<-[:ASSIGNED_TO]-(r:ServiceRequest)<-[:FILED]-(c:Citizen) "
            "OPTIONAL MATCH (d)-[:COVERS]->(a:Area) "
            "RETURN d.name AS department, "
            "       COLLECT(DISTINCT c.name) AS affected_citizens, "
            "       COLLECT(DISTINCT a.name) AS affected_areas, "
            "       COUNT(DISTINCT r) AS requests_orphaned",
            name=dept_name,
        ).single()
    return dict(row) if row else {}


def query_collaboration_gaps():
    """Departments that share area coverage but have no formal collaboration edge."""
    with get_driver().session() as s:
        result = s.run(
            "MATCH (d1:Department)-[:COVERS]->(a:Area)<-[:COVERS]-(d2:Department) "
            "WHERE d1.id < d2.id "
            "  AND NOT (d1)-[:COLLABORATES_WITH]-(d2) "
            "RETURN d1.name AS dept_a, d2.name AS dept_b, "
            "       COLLECT(a.name) AS shared_areas, COUNT(a) AS overlap_count "
            "ORDER BY overlap_count DESC"
        )
        return [dict(r) for r in result]


# ── Visual graph (nodes + edges for vis.js) ───────────────────────────────────

COLOR_MAP = {
    "Citizen": "#059669", "Department": "#1d4ed8", "Area": "#d97706",
    "Technician": "#7c3aed", "ServiceRequest": "#dc2626",
}
SHAPE_MAP = {
    "Citizen": "dot", "Department": "diamond", "Area": "triangle",
    "Technician": "star", "ServiceRequest": "square",
}


def query_visual_graph(limit=150):
    with get_driver().session() as s:
        rows = s.run(
            "MATCH (a)-[r]->(b) "
            "RETURN id(a) AS sid, labels(a)[0] AS sl, a.name AS sn, a.id AS sk, a.category AS sc, "
            "       type(r) AS rel, "
            "       id(b) AS tid, labels(b)[0] AS tl, b.name AS tn, b.id AS tk, b.category AS tc "
            "LIMIT $limit",
            limit=limit,
        )
        nodes, edges = {}, []
        for row in rows:
            for prefix in (("s", "sid", "sl", "sn", "sk", "sc"),
                           ("t", "tid", "tl", "tn", "tk", "tc")):
                p, nid_k, lbl_k, name_k, key_k, cat_k = prefix
                nid  = row[nid_k]
                lbl  = row[lbl_k]
                name = row[name_k] or row[cat_k] or row[key_k]
                if nid not in nodes:
                    nodes[nid] = {
                        "id": nid, "label": name or str(nid),
                        "group": lbl,
                        "color": COLOR_MAP.get(lbl, "#888"),
                        "shape": SHAPE_MAP.get(lbl, "dot"),
                    }
            edges.append({"from": row["sid"], "to": row["tid"], "label": row["rel"]})
    return {"nodes": list(nodes.values()), "edges": edges}