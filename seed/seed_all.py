"""
Seed Script — Populate all 4 databases with sample data
Run: python seed/seed_all.py
"""

import sys, os
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import mongo_client as mongo
from db import neo4j_client as neo4j
from db import redis_client as redis_c
from db import elasticsearch_client as es


AREAS = [
    {"id": "dist_1", "name": "Old City", "population": 120000},
    {"id": "dist_2", "name": "Commercial Center", "population": 95000},
    {"id": "dist_3", "name": "University Zone", "population": 78000},
    {"id": "dist_4", "name": "Northern Suburbs", "population": 110000},
    {"id": "dist_5", "name": "Industrial Area", "population": 64000},
    {"id": "dist_6", "name": "Residential East", "population": 105000},
    {"id": "dist_7", "name": "Residential West", "population": 97000},
    {"id": "dist_8", "name": "Southern Zone", "population": 88000},
]

DEPARTMENTS = [
    {"id": "dept_public_works", "name": "Public Works", "categories": ["infrastructure", "traffic"]},
    {"id": "dept_traffic", "name": "Traffic Authority", "categories": ["traffic"]},
    {"id": "dept_sanitation", "name": "Sanitation", "categories": ["waste"]},
    {"id": "dept_lighting", "name": "Street Lighting", "categories": ["lighting"]},
    {"id": "dept_emergency", "name": "Emergency Services", "categories": ["emergency"]},
    {"id": "dept_utilities", "name": "Water & Utilities", "categories": ["water"]},
]

TECHNICIANS = [
    {"id": "tech_1", "name": "Khaled Hassan",  "dept": "dept_lighting"},
    {"id": "tech_2", "name": "Omar Nasser",    "dept": "dept_sanitation"},
    {"id": "tech_3", "name": "Yusuf Kareem",   "dept": "dept_traffic"},
    {"id": "tech_4", "name": "Bilal Mansour",  "dept": "dept_public_works"},
    {"id": "tech_5", "name": "Tariq Saleh",    "dept": "dept_utilities"},
]

CATEGORIES = {
    "waste":        {"default": "medium", "subs": ["Overflowing Bin", "Illegal Dumping", "Blocked Drainage"]},
    "lighting":     {"default": "medium", "subs": ["Broken Lamp Post", "Unlit Zone", "Flickering Light"]},
    "traffic":      {"default": "medium", "subs": ["Pothole", "Road Closure", "Signal Failure", "Congestion"]},
    "infrastructure": {"default": "medium", "subs": ["Broken Bench", "Damaged Sidewalk", "Graffiti"]},
    "water":        {"default": "high", "subs": ["Water Leak", "Sewage Issue"]},
    "emergency":    {"default": "high", "subs": ["Flooding", "Fire", "Public Hazard"]},
}

CITIZENS = [
    {"name": "Ahmed Al-Khalidi",  "email": "ahmed@example.com",  "national_id": "9001001", "phone": "0591234567", "area": "dist_3"},
    {"name": "Fatima Nasser",     "email": "fatima@example.com", "national_id": "9001002", "phone": "0592345678", "area": "dist_1"},
    {"name": "Omar Barakat",      "email": "omar@example.com",   "national_id": "9001003", "phone": "0593456789", "area": "dist_2"},
    {"name": "Layla Mustafa",     "email": "layla@example.com",  "national_id": "9001004", "phone": "0594567890", "area": "dist_4"},
    {"name": "Yusuf Haddad",      "email": "yusuf@example.com",  "national_id": "9001005", "phone": "0595678901", "area": "dist_5"},
]

REQUESTS = [
    {"category": "lighting", "sub": "Broken Lamp Post", "desc": "Lamp post on Al-Najah Street is out for 3 nights", "lat": 31.901, "lng": 35.202, "area": "dist_3", "citizen_idx": 0},
    {"category": "waste", "sub": "Overflowing Bin", "desc": "Garbage bin near central market is overflowing", "lat": 31.894, "lng": 35.196, "area": "dist_1", "citizen_idx": 1},
    {"category": "traffic", "sub": "Pothole", "desc": "Deep pothole on main road causing accidents", "lat": 31.909, "lng": 35.209, "area": "dist_2", "citizen_idx": 2},
    {"category": "water", "sub": "Water Leak", "desc": "Water pipe leaking near the roundabout", "lat": 31.924, "lng": 35.219, "area": "dist_4", "citizen_idx": 3},
    {"category": "infrastructure", "sub": "Broken Bench", "desc": "Park bench is broken and dangerous", "lat": 31.879, "lng": 35.184, "area": "dist_5", "citizen_idx": 4},
    {"category": "waste", "sub": "Illegal Dumping", "desc": "Large pile of illegal waste dumped on side road", "lat": 31.900, "lng": 35.200, "area": "dist_3", "citizen_idx": 0},
    {"category": "lighting", "sub": "Unlit Zone", "desc": "Entire street section has no lighting at night", "lat": 31.893, "lng": 35.195, "area": "dist_1", "citizen_idx": 1},
    {"category": "traffic", "sub": "Signal Failure", "desc": "Traffic lights at main junction are not working", "lat": 31.912, "lng": 35.212, "area": "dist_2", "citizen_idx": 2},
]


def seed_all():
    print("\nSeeding all databases...\n")

    # 1. Init schemas (indexes for Mongo, constraints for Neo4j)
    mongo.init_indexes()
    neo4j.init_constraints()
    neo4j.seed_static_nodes()

    # 2. Reference data (Mongo)
    for area in AREAS:
        mongo.upsert_area(area["id"], area["name"], population=area.get("population"))

    for dept in DEPARTMENTS:
        mongo.upsert_department(
            dept_id=dept["id"],
            name=dept["name"],
            contact_email=f"{dept['id']}@smartcity.local",
            contact_phone="+970-000-0000",
            service_categories=dept["categories"],
            areas=[a["id"] for a in AREAS],
        )

    for name, cfg in CATEGORIES.items():
        mongo.upsert_category(name, cfg["default"], cfg["subs"])

    for tech in TECHNICIANS:
        dept = next((d for d in DEPARTMENTS if d["id"] == tech["dept"]), None)
        mongo.upsert_technician(
            tech_id=tech["id"],
            name=tech["name"],
            department_id=tech["dept"],
            department_name=dept["name"] if dept else "",
        )

    # 3. Seed citizens + users
    citizen_ids = []
    for c in CITIZENS:
        area = next(a for a in AREAS if a["id"] == c["area"])
        citizen_id = mongo.create_citizen(
            national_id=c["national_id"],
            name=c["name"],
            email=c["email"],
            phone=c["phone"],
            area_id=area["id"],
            area_name=area["name"],
        )
        if citizen_id is None:
            existing = mongo.get_citizen_by_email(c["email"])
            citizen_id = existing["_id"]

        user_id = mongo.create_user(
            username=c["name"],
            email=c["email"],
            password_hash=generate_password_hash("demo"),
            role="citizen",
            citizen_id=citizen_id,
        )
        if user_id is None:
            user = mongo.get_user_by_email(c["email"])
            user_id = user["_id"] if user else None

        citizen_ids.append(citizen_id)

        neo4j.create_citizen_node(citizen_id, c["name"], area["id"])
        redis_c.update_leaderboard(citizen_id, 0)

        print(f"  Citizen: {c['name']} -> {citizen_id}")

    # 3b. Seed technician login accounts (profile docs were created above)
    print("")
    for tech in TECHNICIANS:
        email = f"{tech['id']}@smartcity.local"
        user_id = mongo.create_user(
            username=tech["name"],
            email=email,
            password_hash=generate_password_hash("demo"),
            role="technician",
            technician_id=tech["id"],
        )
        if user_id is None:
            existing = mongo.get_user_by_email(email)
            user_id = existing["_id"] if existing else None
        print(f"  Technician account: {email} -> {tech['name']}")

    # 3c. Seed city-manager login accounts
    print("")
    MANAGERS = [
        {"name": "Saad Misk",        "email": "saad@example.com"},
        {"name": "Manager Haitham",  "email": "manager@example.com"},
    ]
    for m in MANAGERS:
        user_id = mongo.create_user(
            username=m["name"],
            email=m["email"],
            password_hash=generate_password_hash("demo"),
            role="manager",
        )
        if user_id is None:
            existing = mongo.get_user_by_email(m["email"])
            user_id = existing["_id"] if existing else None
        print(f"  Manager account: {m['email']} -> {m['name']}")
    print("")

    # 4. Seed requests
    request_ids = []
    for req in REQUESTS:
        cid = citizen_ids[req["citizen_idx"]]
        citizen = mongo.get_citizen_by_id(cid)
        area = next(a for a in AREAS if a["id"] == req["area"])

        dept = mongo.get_department_for_category(req["category"]) or {}
        assignment = {
            "departmentId": dept.get("departmentId"),
            "departmentName": dept.get("departmentName"),
            "technicianId": None,
            "technicianName": None,
        }
        priority = mongo.get_default_priority(req["category"])

        rid = mongo.create_service_request(
            citizen_id=cid,
            citizen_name=citizen.get("name"),
            category=req["category"],
            sub_category=req["sub"],
            description=req["desc"],
            area_id=area["id"],
            area_name=area["name"],
            area_description="",
            lat=req["lat"],
            lng=req["lng"],
            priority=priority,
            assignment=assignment,
        )
        request_ids.append(rid)

        es.index_request(rid, {
            "category": req["category"],
            "subCategory": req["sub"],
            "description": req["desc"],
            "areaName": area["name"],
            "status": "pending",
            "priority": priority,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "citizenName": citizen.get("name"),
        })

        neo4j.create_request_node(rid, req["category"], cid, assignment.get("departmentId"))
        neo4j.link_request_to_area(rid, area["id"])

        redis_c.cache_request_status(rid, "pending")
        redis_c.push_recent_request(cid, rid)

        print(f"  Request: [{req['category']}] {req['sub']} -> {rid}")

    # 5. Simulate resolutions
    extra_resolutions = [
        (0, "tech_1"),
        (1, "tech_2"),
        (2, "tech_3"),
        (4, "tech_4"),
    ]
    for idx, tech in extra_resolutions:
        if idx < len(request_ids):
            rid = request_ids[idx]
            tech_doc = next((t for t in TECHNICIANS if t["id"] == tech), None)
            dept = next((d for d in DEPARTMENTS if d["id"] == tech_doc["dept"]), None) if tech_doc else None
            assignment_update = {
                "departmentId": dept["id"] if dept else None,
                "departmentName": dept["name"] if dept else None,
                "technicianId": tech_doc["id"] if tech_doc else None,
                "technicianName": tech_doc["name"] if tech_doc else None,
            }
            mongo.update_request_status(rid, "resolved", assignment_update)
            if tech_doc:
                neo4j.mark_request_resolved(rid, tech_doc["id"])
            redis_c.invalidate_request_status(rid)
            redis_c.cache_request_status(rid, "resolved")
            print(f"  Resolved: request {rid} by {tech}")

    redis_c.get_category_list()

    print("\nAll databases seeded successfully.\n")
    print("  MongoDB      -> users, citizens, service_requests, reference data")
    print("  Neo4j        -> citizen/dept/area graph")
    print("  Redis        -> sessions, status cache, leaderboard")
    print("  Elasticsearch-> similarity index\n")


if __name__ == "__main__":
    seed_all()
