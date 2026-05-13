"""
MongoDB Client — Citizen profiles, Service Requests, Departments, GeoPoints
Member responsible: Haitham
"""

import os
from datetime import datetime, timezone
from pymongo import MongoClient, GEOSPHERE
from pymongo.errors import DuplicateKeyError
from bson import ObjectId


def get_db():
    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/smartcity")
    client = MongoClient(uri)
    return client.get_default_database()


def init_mongo():
    """Create collections, indexes, and constraints."""
    db = get_db()

    # Indexes
    db.users.create_index("email", unique=True)
    db.users.create_index("national_id", unique=True)
    db.requests.create_index([("location", GEOSPHERE)])
    db.requests.create_index("citizen_id")
    db.requests.create_index("status")
    db.requests.create_index("category")
    db.requests.create_index("district_id")
    db.requests.create_index("created_at")

    print("✅ MongoDB indexes created.")
    return db


# ─────────────────────────────────────────────
# USERS (Citizens)
# ─────────────────────────────────────────────

def create_user(name, email, national_id, phone, district_id, lat, lng, language="ar"):
    db = get_db()
    user = {
        "name": name,
        "email": email,
        "national_id": national_id,
        "phone": phone,
        "district_id": district_id,
        "home_location": {
            "type": "Point",
            "coordinates": [lng, lat]   # GeoJSON: [longitude, latitude]
        },
        "language": language,
        "notify_categories": [],
        "civic_score": 0,
        "badges": [],
        "created_at": datetime.now(timezone.utc)
    }
    try:
        result = db.users.insert_one(user)
        return str(result.inserted_id)
    except DuplicateKeyError:
        return None


def get_user_by_email(email):
    db = get_db()
    user = db.users.find_one({"email": email})
    if user:
        user["_id"] = str(user["_id"])
    return user


def get_user_by_id(user_id):
    db = get_db()
    user = db.users.find_one({"_id": ObjectId(user_id)})
    if user:
        user["_id"] = str(user["_id"])
    return user


def update_civic_score(user_id, delta=1):
    db = get_db()
    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$inc": {"civic_score": delta}}
    )


# ─────────────────────────────────────────────
# SERVICE REQUESTS
# ─────────────────────────────────────────────

VALID_STATUSES = ["OPEN", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED", "REJECTED"]

def create_request(citizen_id, category, subcategory, description,
                   lat, lng, district_id, photo_url=None):
    db = get_db()

    # Auto-assign department based on category
    dept_map = {
        "waste":        "dept_sanitation",
        "lighting":     "dept_lighting",
        "traffic":      "dept_traffic",
        "infrastructure": "dept_public_works",
        "water":        "dept_utilities",
        "emergency":    "dept_emergency",
    }
    dept_id = dept_map.get(category, "dept_public_works")

    req = {
        "citizen_id":   citizen_id,
        "category":     category,
        "subcategory":  subcategory,
        "description":  description,
        "location": {
            "type": "Point",
            "coordinates": [lng, lat]
        },
        "district_id":  district_id,
        "photo_url":    photo_url,
        "status":       "OPEN",
        "assigned_dept": dept_id,
        "assigned_tech": None,
        "priority":     _calc_priority(category),
        "status_history": [
            {
                "status":    "OPEN",
                "timestamp": datetime.now(timezone.utc),
                "actor":     citizen_id,
                "comment":   "Request submitted by citizen"
            }
        ],
        "satisfaction_rating": None,
        "created_at":   datetime.now(timezone.utc),
        "resolved_at":  None
    }
    result = db.requests.insert_one(req)
    return str(result.inserted_id)


def _calc_priority(category):
    priority_map = {
        "emergency": 1,
        "water":     2,
        "traffic":   2,
        "lighting":  3,
        "waste":     3,
        "infrastructure": 4,
    }
    return priority_map.get(category, 3)


def update_request_status(request_id, new_status, actor, comment=""):
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {new_status}")
    db = get_db()
    now = datetime.now(timezone.utc)
    update = {
        "$set":  {"status": new_status},
        "$push": {
            "status_history": {
                "status":    new_status,
                "timestamp": now,
                "actor":     actor,
                "comment":   comment
            }
        }
    }
    if new_status in ("RESOLVED", "CLOSED"):
        update["$set"]["resolved_at"] = now

    db.requests.update_one({"_id": ObjectId(request_id)}, update)


def get_requests_by_citizen(citizen_id):
    db = get_db()
    reqs = list(db.requests.find({"citizen_id": citizen_id}).sort("created_at", -1))
    for r in reqs:
        r["_id"] = str(r["_id"])
    return reqs


def get_request_by_id(request_id):
    db = get_db()
    r = db.requests.find_one({"_id": ObjectId(request_id)})
    if r:
        r["_id"] = str(r["_id"])
    return r


# ─────────────────────────────────────────────
# GEOSPATIAL QUERY
# ─────────────────────────────────────────────

def find_nearby_requests(lat, lng, max_distance_m=500, category=None):
    """Find unresolved requests within max_distance_m meters of a point."""
    db = get_db()
    query = {
        "location": {
            "$near": {
                "$geometry": {"type": "Point", "coordinates": [lng, lat]},
                "$maxDistance": max_distance_m
            }
        },
        "status": {"$ne": "RESOLVED"}
    }
    if category:
        query["category"] = category

    results = list(db.requests.find(query).limit(50))
    for r in results:
        r["_id"] = str(r["_id"])
    return results


# ─────────────────────────────────────────────
# ANALYTICS — Aggregation Pipeline
# ─────────────────────────────────────────────

def analytics_top_issues(days=30, limit=5):
    """Most reported issue categories in last N days."""
    db = get_db()
    from datetime import timedelta
    since = datetime.now(timezone.utc) - timedelta(days=days)

    pipeline = [
        {"$match": {"created_at": {"$gte": since}}},
        {"$group": {
            "_id": "$category",
            "count": {"$sum": 1},
            "open":  {"$sum": {"$cond": [{"$eq": ["$status", "OPEN"]}, 1, 0]}},
        }},
        {"$sort": {"count": -1}},
        {"$limit": limit},
        {"$project": {"category": "$_id", "count": 1, "open": 1, "_id": 0}}
    ]
    return list(db.requests.aggregate(pipeline))


def analytics_by_district(days=30):
    """Request counts per district."""
    db = get_db()
    from datetime import timedelta
    since = datetime.now(timezone.utc) - timedelta(days=days)

    pipeline = [
        {"$match": {"created_at": {"$gte": since}}},
        {"$group": {
            "_id": "$district_id",
            "total":    {"$sum": 1},
            "resolved": {"$sum": {"$cond": [{"$eq": ["$status", "RESOLVED"]}, 1, 0]}},
        }},
        {"$sort": {"total": -1}},
        {"$project": {"district": "$_id", "total": 1, "resolved": 1, "_id": 0}}
    ]
    return list(db.requests.aggregate(pipeline))


def analytics_avg_response_time():
    """Average resolution time per department (in hours)."""
    db = get_db()
    pipeline = [
        {"$match": {"resolved_at": {"$ne": None}}},
        {"$project": {
            "dept": "$assigned_dept",
            "hours": {
                "$divide": [
                    {"$subtract": ["$resolved_at", "$created_at"]},
                    3600000  # ms → hours
                ]
            }
        }},
        {"$group": {
            "_id":      "$dept",
            "avg_hours": {"$avg": "$hours"},
            "count":    {"$sum": 1}
        }},
        {"$sort": {"avg_hours": 1}},
        {"$project": {"department": "$_id", "avg_hours": 1, "count": 1, "_id": 0}}
    ]
    return list(db.requests.aggregate(pipeline))


def analytics_overview():
    """Quick stats for the dashboard header."""
    db = get_db()
    total     = db.requests.count_documents({})
    open_cnt  = db.requests.count_documents({"status": "OPEN"})
    resolved  = db.requests.count_documents({"status": "RESOLVED"})
    citizens  = db.users.count_documents({})
    return {
        "total_requests": total,
        "open_requests":  open_cnt,
        "resolved":       resolved,
        "citizens":       citizens
    }
