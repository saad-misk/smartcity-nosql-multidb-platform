"""
Routes — Graph Queries (Neo4j / Cypher)

Organised by complexity:
    A. Basic         — schema overview, simple lookups
    B. Intermediate  — cross-node analytics
    C. Advanced      — graph-only power (shortest path, impact, gaps)
    Visual           — nodes + edges for vis.js
"""

from flask import Blueprint, jsonify, request
from db import neo4j_client as neo4j

graph_bp = Blueprint("graph", __name__)


# ─── A. Basic ───────────────────────────────────────────────────────────────

@graph_bp.route("/api/graph/stats", methods=["GET"])
def graph_stats():
    """Node and relationship counts for the dashboard."""
    return jsonify(neo4j.query_graph_stats()), 200


@graph_bp.route("/api/graph/department-coverage", methods=["GET"])
def department_coverage():
    """Which areas each department covers."""
    rows = neo4j.query_department_coverage()
    return jsonify({"department_coverage": rows}), 200


@graph_bp.route("/api/graph/citizen/<citizen_id>/requests", methods=["GET"])
def citizen_requests(citizen_id):
    """All requests filed by a given citizen."""
    rows = neo4j.query_citizen_requests(citizen_id)
    return jsonify({"citizen_id": citizen_id, "requests": rows}), 200


# ─── B. Intermediate ────────────────────────────────────────────────────────

@graph_bp.route("/api/graph/area-workload", methods=["GET"])
def area_workload():
    """Areas ranked by number of open (pending) requests."""
    rows = neo4j.query_area_workload()
    return jsonify({"area_workload": rows}), 200


@graph_bp.route("/api/graph/department-efficiency", methods=["GET"])
def department_efficiency():
    """Resolved vs total requests per department, with resolution rate."""
    rows = neo4j.query_department_efficiency()
    return jsonify({"department_efficiency": rows}), 200


@graph_bp.route("/api/graph/top-technicians", methods=["GET"])
def top_technicians():
    """Technicians ranked by number of resolved requests."""
    limit = request.args.get("limit", 5, type=int)
    rows  = neo4j.query_top_technicians(limit)
    return jsonify({"top_technicians": rows}), 200


# ─── C. Advanced / Graph-Only ────────────────────────────────────────────────

@graph_bp.route("/api/graph/shortest-path", methods=["GET"])
def shortest_path():
    """Shortest connection path between a citizen and a department."""
    from_name = request.args.get("from", "Ahmed Al-Khalidi")
    to_name   = request.args.get("to",   "Emergency Services")
    rows = neo4j.query_shortest_path(from_name, to_name)
    return jsonify({"from": from_name, "to": to_name, "path": rows}), 200


@graph_bp.route("/api/graph/impact-analysis", methods=["GET"])
def impact_analysis():
    """If a department goes offline: affected citizens, areas, orphaned requests."""
    dept = request.args.get("department", "Sanitation")
    return jsonify({"impact_analysis": neo4j.query_impact_analysis(dept)}), 200


@graph_bp.route("/api/graph/collaboration-gaps", methods=["GET"])
def collaboration_gaps():
    """Departments that share area coverage but have no formal collaboration edge."""
    rows = neo4j.query_collaboration_gaps()
    return jsonify({"collaboration_gaps": rows}), 200


# ─── Visual graph ────────────────────────────────────────────────────────────

@graph_bp.route("/api/graph/visual", methods=["GET"])
def visual_graph():
    """Full graph as nodes + edges for vis.js rendering."""
    limit = request.args.get("limit", 150, type=int)
    return jsonify(neo4j.query_visual_graph(limit)), 200
