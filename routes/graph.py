"""
Routes — Graph Queries (Neo4j / Cypher)
"""

from flask import Blueprint, jsonify, request
from db import neo4j_client as neo4j

graph_bp = Blueprint("graph", __name__)


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
