"""
Routes — Analytics & Reporting (MongoDB Aggregation Pipeline)
"""

from flask import Blueprint, jsonify, request
from db import mongo_client     as mongo
from db import cassandra_client as cass
from db import redis_client     as redis_c

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/api/analytics/overview", methods=["GET"])
def overview():
    data = mongo.analytics_overview()
    redis_info = redis_c.get_redis_info()
    data["redis"] = redis_info
    return jsonify(data), 200


@analytics_bp.route("/api/analytics/top-issues", methods=["GET"])
def top_issues():
    days  = request.args.get("days",  30,  type=int)
    limit = request.args.get("limit", 5,   type=int)
    data  = mongo.analytics_top_issues(days=days, limit=limit)
    return jsonify({"period_days": days, "top_issues": data}), 200


@analytics_bp.route("/api/analytics/by-district", methods=["GET"])
def by_district():
    days = request.args.get("days", 30, type=int)
    data = mongo.analytics_by_district(days=days)
    return jsonify({"period_days": days, "districts": data}), 200


@analytics_bp.route("/api/analytics/response-time", methods=["GET"])
def response_time():
    data = mongo.analytics_avg_response_time()
    return jsonify({"departments": data}), 200


@analytics_bp.route("/api/analytics/cassandra/events", methods=["GET"])
def cassandra_events():
    district_id = request.args.get("district_id", "dist_1")
    try:
        events = cass.get_recent_events(district_id, limit=20)
        stats  = cass.get_daily_stats(district_id, days=7)
        return jsonify({"district": district_id, "events": events, "daily_stats": stats}), 200
    except Exception as e:
        return jsonify({"error": str(e), "note": "Cassandra may not be ready yet"}), 503


@analytics_bp.route("/api/analytics/leaderboard", methods=["GET"])
def leaderboard():
    top = redis_c.get_top_citizens(limit=10)
    return jsonify([{"user_id": uid, "civic_score": int(score)} for uid, score in top]), 200
