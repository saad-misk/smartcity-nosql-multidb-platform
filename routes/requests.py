"""
Routes — Service Request Submission, Tracking, Status Updates
This demonstrates the key multi-DB integration flow:
    Submit → Elasticsearch (similarity) + MongoDB (store) + Neo4j (graph edge) + Redis (cache + recent)
"""

from datetime import datetime
from flask import Blueprint, request, jsonify
from db import mongo_client as mongo
from db import neo4j_client as neo4j
from db import redis_client as redis_c
from db import elasticsearch_client as es

requests_bp = Blueprint("requests", __name__)

VALID_STATUSES = ["pending", "assigned", "in_progress", "resolved"]
PRIORITY_ORDER = ["low", "medium", "high"]


def _require_session(req):
    token = req.headers.get("X-Session-Token")
    if not token:
        return None, None
    sess = redis_c.get_session(token)
    if not sess:
        return None, None
    return token, sess


def _boost_priority(priority, similarity_score, threshold=5.0):
    if similarity_score < threshold:
        return priority, False
    if priority not in PRIORITY_ORDER:
        return priority, False
    idx = PRIORITY_ORDER.index(priority)
    boosted = PRIORITY_ORDER[min(idx + 1, len(PRIORITY_ORDER) - 1)]
    return boosted, boosted != priority


# ─────────────────────────────────────────────
# SUBMIT A REQUEST
# ─────────────────────────────────────────────

@requests_bp.route("/api/requests", methods=["POST"])
def submit_request():
    token, sess = _require_session(request)
    if not sess:
        return jsonify({"error": "Unauthorized — session expired or missing"}), 401

    data = request.json or {}
    required = ["category", "subCategory", "description", "lat", "lng", "areaId", "areaName"]
    if not all(k in data for k in required):
        return jsonify({"error": "Missing required fields"}), 400

    citizen_id = sess.get("citizen_id") or sess.get("user_id")
    category = data["category"]
    sub_category = data["subCategory"]
    area_id = data["areaId"]
    area_name = data["areaName"]
    area_description = data.get("areaDescription", "")

    citizen = mongo.get_citizen_by_id(citizen_id)
    if not citizen:
        return jsonify({"error": "Citizen not found"}), 404

    base_priority = mongo.get_default_priority(category)
    similarity_score, similar_hits = es.search_similar_requests(
        description=data["description"],
        category=category,
        sub_category=sub_category,
        area_name=area_name,
        limit=3,
    )
    priority, boosted = _boost_priority(base_priority, similarity_score)
    similar_ids = [h["requestId"] for h in similar_hits if h.get("requestId")]

    dept = mongo.get_department_for_category(category) or {}
    assignment = {
        "departmentId": dept.get("departmentId"),
        "departmentName": dept.get("departmentName"),
        "technicianId": None,
        "technicianName": None,
    }

    # 1. Store in MongoDB
    rid = mongo.create_service_request(
        citizen_id=citizen_id,
        citizen_name=citizen.get("name"),
        category=category,
        sub_category=sub_category,
        description=data["description"],
        area_id=area_id,
        area_name=area_name,
        area_description=area_description,
        lat=float(data["lat"]),
        lng=float(data["lng"]),
        priority=priority,
        assignment=assignment,
        photo_urls=data.get("photoUrls") or [],
        similarity_score=similarity_score,
        similar_request_ids=similar_ids,
    )

    # 2. Index in Elasticsearch for future similarity checks
    es.index_request(rid, {
        "category": category,
        "subCategory": sub_category,
        "description": data["description"],
        "areaName": area_name,
        "status": "pending",
        "priority": priority,
        "createdAt": datetime.utcnow().isoformat(),
        "citizenName": citizen.get("name"),
    })

    # 3. Create graph edges in Neo4j
    dept_id = assignment.get("departmentId")
    neo4j.create_request_node(rid, category, "pending", citizen_id, dept_id)
    neo4j.link_request_to_area(rid, area_id)

    # 4. Cache status in Redis + push to user recent list
    redis_c.cache_request_status(rid, "pending")
    redis_c.push_recent_request(citizen_id, rid)

    # 5. Invalidate department dashboard cache (data changed)
    if dept_id:
        redis_c.invalidate_dept_dashboard(dept_id)

    # 6. Reward civic score
    mongo.update_civic_score(citizen_id, 1)
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
# GET ONE REQUEST (cache-first)
# ─────────────────────────────────────────────

@requests_bp.route("/api/requests/<request_id>", methods=["GET"])
def get_request(request_id):
    # Try Redis cache first
    cached_status = redis_c.get_cached_status(request_id)

    req = mongo.get_request_by_id(request_id)
    if not req:
        return jsonify({"error": "Request not found"}), 404

    req["cache_hit"] = cached_status is not None
    if cached_status:
        req["status"] = cached_status   # serve from cache

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
# UPDATE STATUS (department / technician action)
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

    assignment = req.get("assignment", {})
    assignment_update = {
        "departmentId": data.get("departmentId", assignment.get("departmentId")),
        "departmentName": data.get("departmentName", assignment.get("departmentName")),
        "technicianId": data.get("technicianId", assignment.get("technicianId")),
        "technicianName": data.get("technicianName", assignment.get("technicianName")),
    }

    # 1. Update MongoDB
    mongo.update_request_status(request_id, new_status, assignment_update)

    # 2. Invalidate Redis cache, then re-cache new status
    redis_c.invalidate_request_status(request_id)
    redis_c.cache_request_status(request_id, new_status)

    # 3. Invalidate dept dashboard
    dept_id = assignment_update.get("departmentId")
    if dept_id:
        redis_c.invalidate_dept_dashboard(dept_id)

    # 4. If resolved — update Neo4j graph
    if new_status == "resolved" and assignment_update.get("technicianId"):
        neo4j.mark_request_resolved(request_id, assignment_update["technicianId"])

    return jsonify({"message": f"Status updated to {new_status}", "cache_invalidated": True}), 200


# ─────────────────────────────────────────────
# GEOSPATIAL NEARBY QUERY
# ─────────────────────────────────────────────

@requests_bp.route("/api/requests/nearby", methods=["GET"])
def nearby_requests():
    lat      = request.args.get("lat", type=float)
    lng      = request.args.get("lng", type=float)
    distance = request.args.get("distance", 500, type=int)
    category = request.args.get("category")

    if lat is None or lng is None:
        return jsonify({"error": "lat and lng required"}), 400

    results = mongo.find_nearby_requests(lat, lng, distance, category)
    return jsonify({"count": len(results), "requests": results}), 200


# ─────────────────────────────────────────────
# CATEGORY LIST (Redis-cached)
# ─────────────────────────────────────────────

@requests_bp.route("/api/categories", methods=["GET"])
def get_categories():
    cats = redis_c.get_category_list()
    return jsonify(cats), 200


# ─────────────────────────────────────────────
# ELASTICSEARCH — SIMILARITY SEARCH
# ─────────────────────────────────────────────

@requests_bp.route("/api/search/similar", methods=["GET"])
def search_similar():
    text = request.args.get("q", "").strip()
    if not text:
        return jsonify({"error": "q is required"}), 400

    category = request.args.get("category")
    sub_category = request.args.get("subCategory")
    area_name = request.args.get("areaName")
    score, results = es.search_similar_requests(
        description=text,
        category=category,
        sub_category=sub_category,
        area_name=area_name,
        limit=5,
    )
    return jsonify({
        "query": text,
        "best_score": score,
        "results": results,
    }), 200
