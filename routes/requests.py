"""
Routes — Service Request Submission, Tracking, Status Updates
This demonstrates the key multi-DB integration flow:
  Submit → MongoDB (store) + Neo4j (graph edge) + Redis (cache + recent) + Cassandra (event log)
"""

from flask import Blueprint, request, jsonify
from db import mongo_client   as mongo
from db import neo4j_client   as neo4j
from db import redis_client   as redis_c
from db import cassandra_client as cass

requests_bp = Blueprint("requests", __name__)

DEPT_MAP = {
    "waste":          "dept_sanitation",
    "lighting":       "dept_lighting",
    "traffic":        "dept_traffic",
    "water":          "dept_utilities",
    "infrastructure": "dept_public_works",
    "emergency":      "dept_emergency",
}


def _require_session(req):
    token = req.headers.get("X-Session-Token")
    if not token:
        return None, None
    sess = redis_c.get_session(token)
    if not sess:
        return None, None
    return token, sess


# ─────────────────────────────────────────────
# SUBMIT A REQUEST
# ─────────────────────────────────────────────

@requests_bp.route("/api/requests", methods=["POST"])
def submit_request():
    token, sess = _require_session(request)
    if not sess:
        return jsonify({"error": "Unauthorized — session expired or missing"}), 401

    data = request.json
    required = ["category", "subcategory", "description", "lat", "lng", "district_id"]
    if not all(k in data for k in required):
        return jsonify({"error": "Missing required fields"}), 400

    citizen_id  = sess["user_id"]
    category    = data["category"]
    district_id = data["district_id"]

    # 1. Store in MongoDB
    rid = mongo.create_request(
        citizen_id=citizen_id,
        category=category,
        subcategory=data["subcategory"],
        description=data["description"],
        lat=float(data["lat"]),
        lng=float(data["lng"]),
        district_id=district_id,
        photo_url=data.get("photo_url")
    )

    # 2. Create graph edges in Neo4j
    dept_id = DEPT_MAP.get(category, "dept_public_works")
    neo4j.create_request_node(rid, category, "OPEN", citizen_id, dept_id)

    # 3. Cache status in Redis + push to user recent list
    redis_c.cache_request_status(rid, "OPEN")
    redis_c.push_recent_request(citizen_id, rid)

    # 4. Invalidate department dashboard cache (data changed)
    redis_c.invalidate_dept_dashboard(dept_id)

    # 5. Log to Cassandra event log
    try:
        cass.log_status_change(
            request_id=rid, citizen_id=citizen_id,
            district_id=district_id, category=category,
            old_status="", new_status="OPEN",
            actor=citizen_id, comment="Request submitted"
        )
    except Exception as e:
        print(f"⚠️  Cassandra log failed: {e}")

    # 6. Reward civic score
    mongo.update_civic_score(citizen_id, 1)
    user = mongo.get_user_by_id(citizen_id)
    redis_c.update_leaderboard(citizen_id, user.get("civic_score", 1))

    return jsonify({
        "message":    "Request submitted successfully",
        "request_id": rid,
        "status":     "OPEN",
        "assigned_to": dept_id
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

    reqs = mongo.get_requests_by_citizen(sess["user_id"])
    return jsonify({"requests": reqs, "count": len(reqs)}), 200


# ─────────────────────────────────────────────
# UPDATE STATUS (department / technician action)
# ─────────────────────────────────────────────

@requests_bp.route("/api/requests/<request_id>/status", methods=["PATCH"])
def update_status(request_id):
    data = request.json
    if not data or "status" not in data:
        return jsonify({"error": "New status required"}), 400

    new_status = data["status"]
    actor      = data.get("actor", "system")
    comment    = data.get("comment", "")

    req = mongo.get_request_by_id(request_id)
    if not req:
        return jsonify({"error": "Request not found"}), 404

    old_status = req["status"]

    # 1. Update MongoDB
    mongo.update_request_status(request_id, new_status, actor, comment)

    # 2. Invalidate Redis cache, then re-cache new status
    redis_c.invalidate_request_status(request_id)
    redis_c.cache_request_status(request_id, new_status)

    # 3. Invalidate dept dashboard
    redis_c.invalidate_dept_dashboard(req.get("assigned_dept", ""))

    # 4. If resolved — update Neo4j graph
    if new_status == "RESOLVED" and actor.startswith("tech_"):
        neo4j.mark_request_resolved(request_id, actor)

    # 5. Log to Cassandra
    try:
        cass.log_status_change(
            request_id=request_id,
            citizen_id=req["citizen_id"],
            district_id=req["district_id"],
            category=req["category"],
            old_status=old_status,
            new_status=new_status,
            actor=actor,
            comment=comment
        )
    except Exception as e:
        print(f"⚠️  Cassandra log failed: {e}")

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
