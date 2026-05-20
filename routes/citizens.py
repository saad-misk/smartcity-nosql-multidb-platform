"""
Routes — Citizens: Register, Login, Logout, Profile
"""

from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from db import mongo_client  as mongo
from db import neo4j_client  as neo4j
from db import redis_client  as redis_c

citizens_bp = Blueprint("citizens", __name__)


@citizens_bp.route("/api/register", methods=["POST"])
def register():
    data = request.json or {}
    required = ["name", "email", "national_id", "phone", "area_id", "area_name", "password"]
    if not all(k in data for k in required):
        return jsonify({"error": "Missing required fields"}), 400

    # 1. Create citizen document in MongoDB
    citizen_id = mongo.create_citizen(
        national_id=data["national_id"],
        name=data["name"],
        email=data["email"],
        phone=data["phone"],
        area_id=data["area_id"],
        area_name=data["area_name"],
        language=data.get("language", "en"),
        notification_preference=data.get("notification_preference", "email"),
    )
    if citizen_id is None:
        return jsonify({"error": "Email or national ID already registered"}), 409

    # 2. Create user (auth) document in MongoDB
    user_id = mongo.create_user(
        username=data.get("username") or data["name"],
        email=data["email"],
        password_hash=generate_password_hash(data["password"]),
        role="citizen",
        citizen_id=citizen_id,
    )

    # 3. Create citizen node in Neo4j (links LIVES_IN → Area)
    neo4j.create_citizen_node(citizen_id, data["name"], data["area_id"])

    # 4. Issue a Redis session token
    token = redis_c.create_session(
        user_id, role="citizen",
        citizen_id=citizen_id,
        username=data.get("username") or data["name"],
    )

    return jsonify({"message": "Registered successfully",
                    "token": token, "citizen_id": citizen_id}), 201


@citizens_bp.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}
    if "email" not in data or "password" not in data:
        return jsonify({"error": "email and password required"}), 400

    user = mongo.get_user_by_email(data["email"])
    if not user or not check_password_hash(user["passwordHash"], data["password"]):
        return jsonify({"error": "Invalid credentials"}), 401

    token = redis_c.create_session(
        user["_id"],
        role=user.get("role", "citizen"),
        citizen_id=user.get("citizenId"),
        technician_id=user.get("technicianId"),
        username=user.get("username"),
    )

    citizen = None
    if user.get("citizenId"):
        citizen = mongo.get_citizen_by_id(user["citizenId"])

    return jsonify({
        "message": "Login successful",
        "token": token,
        "user": {
            "id": user["_id"], "username": user.get("username"),
            "email": user.get("email"), "role": user.get("role"),
        },
        "citizen": citizen,
    }), 200


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

    user    = mongo.get_user_by_id(sess["user_id"])
    citizen = mongo.get_citizen_by_id(sess.get("citizen_id")) if sess.get("citizen_id") else None
    recent  = redis_c.get_recent_requests(sess.get("citizen_id") or sess["user_id"])

    return jsonify({"user": user, "citizen": citizen,
                    "recent_request_ids": recent}), 200