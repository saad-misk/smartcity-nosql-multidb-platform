"""
MongoDB Client — SmartCity
Handles: Users, Citizens, ServiceRequests, and reference data (Areas, Departments, Technicians, Categories)
"""

import os
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, GEOSPHERE
from pymongo.errors import DuplicateKeyError
from bson import ObjectId


def get_db():
    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/smartcity")
    return MongoClient(uri).get_default_database()


def init_indexes():
    db = get_db()
    db.users.create_index("email", unique=True)
    db.citizens.create_index("nationalId", unique=True)
    db.citizens.create_index("email", unique=True)
    db.service_requests.create_index([("location.gpsCoordinate", GEOSPHERE)])
    db.service_requests.create_index("citizen.citizenId")
    db.service_requests.create_index("status")
    db.categories.create_index("name", unique=True)
    print("MongoDB indexes ready.")


# ── Helpers ──────────────────────────────────────────────────────────────────

def to_oid(value):
    if isinstance(value, ObjectId):
        return value
    return ObjectId(value) if value and ObjectId.is_valid(value) else value


def clean(doc):
    """Convert _id to string so the document is JSON-serializable."""
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


# ── Users ─────────────────────────────────────────────────────────────────────

def create_user(username, email, password_hash, role="citizen",
                citizen_id=None, technician_id=None):
    try:
        result = get_db().users.insert_one({
            "username": username,
            "email": email,
            "passwordHash": password_hash,
            "role": role,                   # "citizen" | "technician" | "manager"
            "citizenId": citizen_id,
            "technicianId": technician_id,
            "createdAt": datetime.now(timezone.utc),
        })
        return str(result.inserted_id)
    except DuplicateKeyError:
        return None


def get_user_by_email(email):
    return clean(get_db().users.find_one({"email": email}))


def get_user_by_id(user_id):
    return clean(get_db().users.find_one({"_id": to_oid(user_id)}))


# ── Citizens ──────────────────────────────────────────────────────────────────

def create_citizen(national_id, name, email, phone, area_id, area_name,
                   language="en", notification_preference="email"):
    try:
        result = get_db().citizens.insert_one({
            "nationalId": national_id,
            "name": name,
            "email": email,
            "phone": phone,
            "area": {"areaId": area_id, "areaName": area_name},
            "civicScore": 0,
            "language": language,
            "notificationPreference": notification_preference,
            "createdAt": datetime.now(timezone.utc),
        })
        return str(result.inserted_id)
    except DuplicateKeyError:
        return None


def get_citizen_by_id(citizen_id):
    return clean(get_db().citizens.find_one({"_id": to_oid(citizen_id)}))


def get_citizen_by_email(email):
    return clean(get_db().citizens.find_one({"email": email}))


def increment_civic_score(citizen_id, delta=1):
    get_db().citizens.update_one(
        {"_id": to_oid(citizen_id)},
        {"$inc": {"civicScore": delta}}
    )


# ── Reference data (Areas, Departments, Technicians, Categories) ──────────────

def upsert_area(area_id, name, boundary_polygon=None, population=None):
    get_db().areas.update_one(
        {"_id": area_id},
        {"$set": {"name": name, "boundaryPolygon": boundary_polygon or [],
                  "population": population}},
        upsert=True,
    )


def upsert_department(dept_id, name, contact_email=None, contact_phone=None,
                      service_categories=None, areas=None):
    get_db().departments.update_one(
        {"_id": dept_id},
        {"$set": {"name": name, "contactEmail": contact_email,
                  "contactPhone": contact_phone,
                  "serviceCategories": service_categories or [],
                  "areas": areas or []}},
        upsert=True,
    )


def upsert_technician(tech_id, name, department_id, department_name):
    get_db().technicians.update_one(
        {"_id": tech_id},
        {"$set": {"name": name, "departmentId": department_id,
                  "departmentName": department_name,
                  "resolvedCount": 0, "activeRequestIds": [],
                  "createdAt": datetime.now(timezone.utc)}},
        upsert=True,
    )


def upsert_category(name, default_priority="medium", sub_categories=None):
    get_db().categories.update_one(
        {"name": name},
        {"$set": {"name": name, "defaultPriority": default_priority,
                  "subCategories": sub_categories or []}},
        upsert=True,
    )


def get_default_priority(category_name):
    cat = get_db().categories.find_one({"name": category_name})
    return cat.get("defaultPriority", "medium") if cat else "medium"


def get_department_for_category(category_name):
    dept = get_db().departments.find_one({"serviceCategories": category_name})
    if dept:
        return {"departmentId": str(dept["_id"]), "departmentName": dept["name"]}
    return None


# ── Service Requests ──────────────────────────────────────────────────────────

VALID_STATUSES = ["pending", "assigned", "in_progress", "resolved"]


def create_service_request(citizen_id, citizen_name, category, sub_category,
                           description, area_id, area_name, area_description,
                           lat, lng, priority="medium", assignment=None):
    now = datetime.now(timezone.utc)
    result = get_db().service_requests.insert_one({
        "citizen": {"citizenId": citizen_id, "citizenName": citizen_name},
        "category": category,
        "subCategory": sub_category,
        "description": description,
        "location": {
            "gpsCoordinate": {"type": "Point", "coordinates": [lng, lat]},
            "areaId": area_id,
            "areaName": area_name,
            "areaDescription": area_description,
        },
        "status": "pending",
        "priority": priority,
        "assignment": assignment or {
            "departmentId": None, "departmentName": None,
            "technicianId": None, "technicianName": None,
        },
        "timestamps": {"createdAt": now, "assignedAt": None, "resolvedAt": None},
        "photoUrls": [],
        "satisfactionRate": None,
        "createdAt": now,
        "updatedAt": now,
    })
    return str(result.inserted_id)


def get_request_by_id(request_id):
    r = get_db().service_requests.find_one({"_id": to_oid(request_id)})
    return clean(r)


def get_requests_by_citizen(citizen_id):
    docs = get_db().service_requests.find(
        {"citizen.citizenId": citizen_id}
    ).sort("createdAt", -1)
    return [clean(r) for r in docs]


def update_request_status(request_id, new_status, assignment_update=None):
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {new_status}")
    now = datetime.now(timezone.utc)
    fields = {"status": new_status, "updatedAt": now}
    if new_status == "assigned":
        fields["timestamps.assignedAt"] = now
    if new_status == "resolved":
        fields["timestamps.resolvedAt"] = now
    if assignment_update:
        fields["assignment"] = assignment_update
    get_db().service_requests.update_one(
        {"_id": to_oid(request_id)}, {"$set": fields}
    )


def find_nearby_requests(lat, lng, max_distance_m=500, category=None):
    """Geospatial query — open requests within N metres of a GPS point."""
    query = {
        "location.gpsCoordinate": {
            "$near": {
                "$geometry": {"type": "Point", "coordinates": [lng, lat]},
                "$maxDistance": max_distance_m,
            }
        },
        "status": {"$ne": "resolved"},
    }
    if category:
        query["category"] = category
    docs = get_db().service_requests.find(query).limit(50)
    return [clean(r) for r in docs]


# ── Analytics (Aggregation Pipelines) ────────────────────────────────────────

def analytics_overview():
    db = get_db()
    return {
        "total_requests": db.service_requests.count_documents({}),
        "open_requests":  db.service_requests.count_documents({"status": "pending"}),
        "resolved":       db.service_requests.count_documents({"status": "resolved"}),
        "citizens":       db.citizens.count_documents({}),
    }


def analytics_top_issues(days=30, limit=5):
    """Most reported categories in the last N days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    pipeline = [
        {"$match": {"createdAt": {"$gte": since}}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": limit},
        {"$project": {"category": "$_id", "count": 1, "_id": 0}},
    ]
    return list(get_db().service_requests.aggregate(pipeline))


def analytics_by_area(days=30):
    """Total and resolved request counts per area."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    pipeline = [
        {"$match": {"createdAt": {"$gte": since}}},
        {"$group": {
            "_id": {"areaId": "$location.areaId", "areaName": "$location.areaName"},
            "total":    {"$sum": 1},
            "resolved": {"$sum": {"$cond": [{"$eq": ["$status", "resolved"]}, 1, 0]}},
        }},
        {"$sort": {"total": -1}},
        {"$project": {"areaId": "$_id.areaId", "areaName": "$_id.areaName",
                      "total": 1, "resolved": 1, "_id": 0}},
    ]
    return list(get_db().service_requests.aggregate(pipeline))


def analytics_avg_resolution_time():
    """Average resolution time (hours) per department."""
    pipeline = [
        {"$match": {"timestamps.resolvedAt": {"$ne": None}}},
        {"$project": {
            "dept": "$assignment.departmentName",
            "hours": {"$divide": [
                {"$subtract": ["$timestamps.resolvedAt", "$timestamps.createdAt"]},
                3_600_000,   # ms → hours
            ]},
        }},
        {"$group": {"_id": "$dept",
                    "avg_hours": {"$avg": "$hours"}, "count": {"$sum": 1}}},
        {"$sort": {"avg_hours": 1}},
        {"$project": {"department": "$_id", "avg_hours": 1, "count": 1, "_id": 0}},
    ]
    return list(get_db().service_requests.aggregate(pipeline))