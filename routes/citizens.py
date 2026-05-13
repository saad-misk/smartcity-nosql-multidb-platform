"""
Routes — Citizen Registration, Login, Logout
"""

from flask import Blueprint, request, jsonify, session
from db import mongo_client as mongo
from db import neo4j_client as neo4j
from db import redis_client as redis_c

citizens_bp = Blueprint("citizens", __name__)


@citizens_bp.route("/api/register", methods=["POST"])
def register():
    data = request.json
    required = ["name", "email", "national_id", "phone", "district_id", "lat", "lng"]
    if not all(k in data for k in required):
        return jsonify({"error": "Missing required fields"}), 400

    uid = mongo.create_user(
        name=data["name"],
        email=data["email"],
        national_id=data["national_id"],
        phone=data["phone"],
        district_id=data["district_id"],
        lat=float(data["lat"]),
        lng=float(data["lng"]),
        language=data.get("language", "ar")
    )
    if uid is None:
        return jsonify({"error": "Email or national ID already registered"}), 409

    # Create graph node
    neo4j.create_citizen_node(uid, data["name"], data["district_id"])

    # Create session
    token = redis_c.create_session(uid)

    return jsonify({"message": "Registered successfully", "token": token, "user_id": uid}), 201


@citizens_bp.route("/api/login", methods=["POST"])
def login():
    data = request.json
    if not data or "email" not in data:
        return jsonify({"error": "Email required"}), 400

    user = mongo.get_user_by_email(data["email"])
    if not user:
        return jsonify({"error": "User not found"}), 404

    token = redis_c.create_session(user["_id"])
    return jsonify({"message": "Login successful", "token": token, "user": {
        "id":    user["_id"],
        "name":  user["name"],
        "email": user["email"],
        "district_id": user.get("district_id"),
        "civic_score": user.get("civic_score", 0),
    }}), 200


@citizens_bp.route("/api/logout", methods=["POST"])
def logout():
    token = request.headers.get("X-Session-Token")
    if token:
        redis_c.delete_session(token)
    return jsonify({"message": "Logged out"}), 200


@citizens_bp.route("/api/me", methods=["GET"])
def me():
    token = request.headers.get("X-Session-Token")
    if not token:
        return jsonify({"error": "No session token"}), 401
    sess = redis_c.get_session(token)
    if not sess:
        return jsonify({"error": "Session expired"}), 401

    user = mongo.get_user_by_id(sess["user_id"])
    if not user:
        return jsonify({"error": "User not found"}), 404

    recent = redis_c.get_recent_requests(sess["user_id"])
    user["recent_request_ids"] = recent
    return jsonify(user), 200
