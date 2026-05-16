"""
Routes — Graph Queries (Neo4j / Cypher)

Category A – Basic (schema understanding)
Category B – Intermediate (analytical value)
Category C – Advanced (graph-only power)
Visual   – Full graph data for vis.js rendering
"""

from flask import Blueprint, jsonify, request
from db import neo4j_client as neo4j

graph_bp = Blueprint("graph", __name__)


# ─── Existing endpoints ─────────────────────────────────────────────────────

@graph_bp.route("/api/graph/stats", methods=["GET"])
def graph_stats():
    data = neo4j.query_graph_stats()
    return jsonify(data), 200


@graph_bp.route("/api/graph/citizen/<citizen_id>/requests", methods=["GET"])
def citizen_requests(citizen_id):
    rows = neo4j.query_citizen_requests(citizen_id)
    return jsonify({"citizen_id": citizen_id, "requests": rows}), 200


@graph_bp.route("/api/graph/department/<dept_id>/technicians", methods=["GET"])
def dept_technicians(dept_id):
    rows = neo4j.query_dept_technicians(dept_id)
    return jsonify({"dept_id": dept_id, "technicians": rows}), 200


@graph_bp.route("/api/graph/shared-districts", methods=["GET"])
def shared_districts():
    rows = neo4j.query_shared_district_departments()
    return jsonify({"shared_district_coverage": rows}), 200


@graph_bp.route("/api/graph/top-technicians", methods=["GET"])
def top_technicians():
    limit = request.args.get("limit", 5, type=int)
    rows  = neo4j.query_top_technicians(limit)
    return jsonify({"top_technicians": rows}), 200


@graph_bp.route("/api/graph/cross-district-reporters", methods=["GET"])
def cross_district_reporters():
    rows = neo4j.query_cross_district_reporters()
    return jsonify({"cross_district_reporters": rows}), 200


# ─── Category A — Basic ─────────────────────────────────────────────────────

@graph_bp.route("/api/graph/department-coverage", methods=["GET"])
def department_coverage():
    """A2. Department → districts coverage map."""
    rows = neo4j.query_department_coverage()
    return jsonify({"department_coverage": rows}), 200


@graph_bp.route("/api/graph/citizen-journey", methods=["GET"])
def citizen_journey():
    """A3. Full request chain for a citizen."""
    name = request.args.get("name", "Ahmed Al-Khalidi")
    rows = neo4j.query_citizen_journey(name)
    return jsonify({"citizen": name, "journey": rows}), 200


# ─── Category B — Intermediate ──────────────────────────────────────────────

@graph_bp.route("/api/graph/district-workload", methods=["GET"])
def district_workload():
    """B3. Districts ranked by open issues."""
    rows = neo4j.query_district_workload()
    return jsonify({"district_workload": rows}), 200


@graph_bp.route("/api/graph/department-efficiency", methods=["GET"])
def department_efficiency():
    """B4. Resolved vs total per department."""
    rows = neo4j.query_department_efficiency()
    return jsonify({"department_efficiency": rows}), 200


# ─── Category C — Advanced / Graph-Only ──────────────────────────────────────

@graph_bp.route("/api/graph/shortest-path", methods=["GET"])
def shortest_path():
    """C1. Shortest path between a citizen and a department."""
    from_name = request.args.get("from", "Ahmed Al-Khalidi")
    to_name   = request.args.get("to", "Emergency Services")
    rows = neo4j.query_shortest_path(from_name, to_name)
    return jsonify({"from": from_name, "to": to_name, "path": rows}), 200


@graph_bp.route("/api/graph/impact-analysis", methods=["GET"])
def impact_analysis():
    """C2. If a department goes down, who is affected?"""
    dept = request.args.get("department", "Sanitation")
    data = neo4j.query_impact_analysis(dept)
    return jsonify({"impact_analysis": data}), 200


@graph_bp.route("/api/graph/collaboration-gaps", methods=["GET"])
def collaboration_gaps():
    """C4. Departments that SHOULD collaborate but don't."""
    rows = neo4j.query_collaboration_gaps()
    return jsonify({"collaboration_gaps": rows}), 200


@graph_bp.route("/api/graph/district-connectivity", methods=["GET"])
def district_connectivity():
    """District health / connectivity score."""
    rows = neo4j.query_district_connectivity()
    return jsonify({"district_connectivity": rows}), 200


@graph_bp.route("/api/graph/explore-district", methods=["GET"])
def explore_district():
    """C5. All entities within N hops of a district."""
    name = request.args.get("name", "University Zone")
    hops = request.args.get("hops", 3, type=int)
    rows = neo4j.query_variable_length_path(name, hops)
    return jsonify({"district": name, "max_hops": hops, "connected": rows}), 200


# ─── Visual Graph ────────────────────────────────────────────────────────────

@graph_bp.route("/api/graph/visual", methods=["GET"])
def visual_graph():
    """Full graph as nodes + edges for vis.js front-end."""
    limit = request.args.get("limit", 150, type=int)
    data  = neo4j.query_visual_graph(limit)
    return jsonify(data), 200
