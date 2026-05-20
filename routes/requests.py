"""
Routes — Service Request Submission, Tracking, Status Updates

This file demonstrates the key multi-DB integration flow:
    Submit -> Elasticsearch (similarity) + MongoDB (store) + Neo4j (graph edge)
              + Redis (cache + recent + leaderboard)
"""

from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from db import mongo_client          as mongo
from db import neo4j_client          as neo4j
from db import redis_client          as redis_c
from db import elasticsearch_client  as es

requests_bp = Blueprint("requests", __name__)

VALID_STATUSES = ["pending", "assigned", "in_progress", "resolved"]
PRIORITY_ORDER = ["low", "medium", "high"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_session(req):
    """Return (token, session_payload) or (None, None) if no valid session."""
    token = req.headers.get("X-Session-Token")
    if not token:
        return None, None
    sess = redis_c.get_session(token)
    if not sess:
        return None, None
    return token, sess


def _boost_priority(priority, similarity_score, threshold=5.0):
    """If a very similar request already exists, bump the priority up one level."""
    if similarity_score < threshold:
        return priority, False
    if priority not in PRIORITY_ORDER:
        return priority, False
    idx = PRIORITY_ORDER.index(priority)
    boosted = PRIORITY_ORDER[min(idx + 1, len(PRIORITY_ORDER) - 1)]
    return boosted, boosted != priority


# ─────────────────────────────────────────────
# SUBMIT A REQUEST  (the main multi-DB flow)
# ─────────────────────────────────────────────

@requests_bp.route("/api/requests", methods=["POST"])
def submit_request():
    token, sess = _require_session(request)
    if not sess:
        return jsonify({"error": "Unauthorized - session expired or missing"}), 401

    data = request.json or {}
    required = ["category", "subCategory", "description", "areaId", "areaName"]
    if not all(k in data for k in required):
        return jsonify({"error": "Missing required fields"}), 400

    citizen_id   = sess.get("citizen_id") or sess.get("user_id")
    category     = data["category"]
    sub_category = data["subCategory"]
    area_id      = data["areaId"]
    area_name    = data["areaName"]
    area_desc    = data.get("areaDescription", "")

    citizen = mongo.get_citizen_by_id(citizen_id)
    if not citizen:
        return jsonify({"error": "Citizen not found"}), 404

    # 0. Default priority from category
    base_priority = mongo.get_default_priority(category)

    # 1. Elasticsearch: check for similar existing requests, maybe boost priority
    similarity_score, similar_hits = es.search_similar(
        description=data["description"],
        category=category,
        area_name=area_name,
        limit=3,
    )
    priority, boosted = _boost_priority(base_priority, similarity_score)

    # 2. Resolve department from category
    dept = mongo.get_department_for_category(category) or {}
    assignment = {
        "departmentId":   dept.get("departmentId"),
        "departmentName": dept.get("departmentName"),
        "technicianId":   None,
        "technicianName": None,
    }

    # 3. Store in MongoDB
    rid = mongo.create_service_request(
        citizen_id=citizen_id,
        citizen_name=citizen.get("name"),
        category=category,
        sub_category=sub_category,
        description=data["description"],
        area_id=area_id,
        area_name=area_name,
        area_description=area_desc,
        lat=float(data.get("lat") or 0),
        lng=float(data.get("lng") or 0),
        priority=priority,
        assignment=assignment,
    )

    # 4. Index in Elasticsearch (so future requests can find this one)
    es.index_request(rid, {
        "category":    category,
        "subCategory": sub_category,
        "description": data["description"],
        "areaName":    area_name,
        "status":      "pending",
        "priority":    priority,
        "createdAt":   datetime.now(timezone.utc).isoformat(),
    })

    # 5. Create graph edges in Neo4j
    dept_id = assignment.get("departmentId")
    if dept_id:
        neo4j.create_request_node(rid, category, citizen_id, dept_id)
        neo4j.link_request_to_area(rid, area_id)

    # 6. Cache status in Redis + push to user's recent list
    redis_c.cache_request_status(rid, "pending")
    redis_c.push_recent_request(citizen_id, rid)

    # 7. Invalidate department dashboard cache (data changed)
    if dept_id:
        redis_c.invalidate_dept_dashboard(dept_id)

    # 8. Reward civic score + update leaderboard
    mongo.increment_civic_score(citizen_id, 1)
    citizen = mongo.get_citizen_by_id(citizen_id)
    redis_c.update_leaderboard(citizen_id, citizen.get("civicScore", 1))

    return jsonify({
        "message": "Request submitted successfully",
        "request_id": rid,
        "status": "pending",
        "priority": priority,
        "similarity_score": similarity_score,
        "similarity_boosted": boosted,
        "assigned_to": dept_id,
    }), 201


# ─────────────────────────────────────────────
# GET ONE REQUEST  (cache-first)
# ─────────────────────────────────────────────

@requests_bp.route("/api/requests/<request_id>", methods=["GET"])
def get_request(request_id):
    cached_status = redis_c.get_cached_status(request_id)

    req = mongo.get_request_by_id(request_id)
    if not req:
        return jsonify({"error": "Request not found"}), 404

    req["cache_hit"] = cached_status is not None
    if cached_status:
        req["status"] = cached_status   # serve newest status from cache
    return jsonify(req), 200


# ─────────────────────────────────────────────
# MY REQUESTS
# ─────────────────────────────────────────────

@requests_bp.route("/api/my-requests", methods=["GET"])
def my_requests():
    token, sess = _require_session(request)
    if not sess:
        return jsonify({"error": "Unauthorized"}), 401

    citizen_id = sess.get("citizen_id") or sess.get("user_id")
    reqs = mongo.get_requests_by_citizen(citizen_id)
    return jsonify({"requests": reqs, "count": len(reqs)}), 200


# ─────────────────────────────────────────────
# UPDATE STATUS  (department / technician action)
# ─────────────────────────────────────────────

@requests_bp.route("/api/requests/<request_id>/status", methods=["PATCH"])
def update_status(request_id):
    data = request.json or {}
    if "status" not in data:
        return jsonify({"error": "New status required"}), 400

    new_status = data["status"]
    if new_status not in VALID_STATUSES:
        return jsonify({"error": "Invalid status"}), 400

    req = mongo.get_request_by_id(request_id)
    if not req:
        return jsonify({"error": "Request not found"}), 404

    assignment = req.get("assignment", {}) or {}
    assignment_update = {
        "departmentId":   data.get("departmentId",   assignment.get("departmentId")),
        "departmentName": data.get("departmentName", assignment.get("departmentName")),
        "technicianId":   data.get("technicianId",   assignment.get("technicianId")),
        "technicianName": data.get("technicianName", assignment.get("technicianName")),
    }

    # 1. Update MongoDB
    mongo.update_request_status(request_id, new_status, assignment_update)

    # 2. Invalidate Redis cache, then re-cache new status
    redis_c.invalidate_request_status(request_id)
    redis_c.cache_request_status(request_id, new_status)

    # 3. Invalidate department dashboard
    dept_id = assignment_update.get("departmentId")
    if dept_id:
        redis_c.invalidate_dept_dashboard(dept_id)

    # 4. If resolved -> update Neo4j graph
    if new_status == "resolved" and assignment_update.get("technicianId"):
        neo4j.mark_request_resolved(request_id, assignment_update["technicianId"])

    return jsonify({"message": f"Status updated to {new_status}",
                    "cache_invalidated": True}), 200


# ─────────────────────────────────────────────
# GEOSPATIAL NEARBY QUERY  (MongoDB $near)
# ─────────────────────────────────────────────

@requests_bp.route("/api/requests/nearby", methods=["GET"])
def nearby_requests():
    lat      = request.args.get("lat",      type=float)
    lng      = request.args.get("lng",      type=float)
    distance = request.args.get("distance", 500, type=int)
    category = request.args.get("category")

    if lat is None or lng is None:
        return jsonify({"error": "lat and lng required"}), 400

    results = mongo.find_nearby_requests(lat, lng, distance, category)
    return jsonify({"count": len(results), "requests": results}), 200


# ─────────────────────────────────────────────
# CATEGORY LIST  (Redis-cached)
# ─────────────────────────────────────────────

@requests_bp.route("/api/categories", methods=["GET"])
def get_categories():
    return jsonify(redis_c.get_category_list()), 200


# ─────────────────────────────────────────────
# ELASTICSEARCH — SIMILARITY SEARCH
# ─────────────────────────────────────────────

@requests_bp.route("/api/search/similar", methods=["GET"])
def search_similar():
    text = request.args.get("q", "").strip()
    if not text:
        return jsonify({"error": "q is required"}), 400

    category  = request.args.get("category")
    area_name = request.args.get("areaName")
    score, results = es.search_similar(
        description=text,
        category=category,
        area_name=area_name,
        limit=5,
    )
    return jsonify({
        "query": text,
        "best_score": score,
        "results": results,
    }), 200
