"""
Routes — Analytics & Reporting (MongoDB Aggregation Pipeline)
"""

from flask import Blueprint, jsonify, request
from db import mongo_client as mongo
from db import redis_client as redis_c

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/api/analytics/overview", methods=["GET"])
def overview():
    data = mongo.analytics_overview()
    data["redis"] = redis_c.get_info()
    return jsonify(data), 200


@analytics_bp.route("/api/analytics/top-issues", methods=["GET"])
def top_issues():
    days  = request.args.get("days",  30,  type=int)
    limit = request.args.get("limit", 5,   type=int)
    data  = mongo.analytics_top_issues(days=days, limit=limit)
    return jsonify({"period_days": days, "top_issues": data}), 200


@analytics_bp.route("/api/analytics/by-area", methods=["GET"])
def by_area():
    days = request.args.get("days", 30, type=int)
    data = mongo.analytics_by_area(days=days)
    return jsonify({"period_days": days, "areas": data}), 200


@analytics_bp.route("/api/analytics/response-time", methods=["GET"])
def response_time():
    data = mongo.analytics_avg_resolution_time()
    return jsonify({"departments": data}), 200


@analytics_bp.route("/api/analytics/leaderboard", methods=["GET"])
def leaderboard():
    top = redis_c.get_top_citizens(limit=10)
    return jsonify([{"user_id": uid, "civic_score": int(score)} for uid, score in top]), 200
