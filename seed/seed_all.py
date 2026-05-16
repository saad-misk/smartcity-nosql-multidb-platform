"""
Seed Script — Populate all 4 databases with sample data
Run: python seed/seed_all.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import mongo_client as mongo
from db import neo4j_client as neo4j
from db import redis_client as redis_c
from db import cassandra_client as cass


# ─── Sample Citizens ────────────────────────────────────────────────────────
CITIZENS = [
    {"name": "Ahmed Al-Khalidi",  "email": "ahmed@example.com",  "national_id": "9001001", "phone": "0591234567", "district": "dist_3", "lat": 31.902, "lng": 35.203},
    {"name": "Fatima Nasser",     "email": "fatima@example.com", "national_id": "9001002", "phone": "0592345678", "district": "dist_1", "lat": 31.895, "lng": 35.197},
    {"name": "Omar Barakat",      "email": "omar@example.com",   "national_id": "9001003", "phone": "0593456789", "district": "dist_2", "lat": 31.910, "lng": 35.210},
    {"name": "Layla Mustafa",     "email": "layla@example.com",  "national_id": "9001004", "phone": "0594567890", "district": "dist_4", "lat": 31.925, "lng": 35.220},
    {"name": "Yusuf Haddad",      "email": "yusuf@example.com",  "national_id": "9001005", "phone": "0595678901", "district": "dist_5", "lat": 31.880, "lng": 35.185},
]

# ─── Sample Requests ────────────────────────────────────────────────────────
REQUESTS = [
    {"category": "lighting",     "sub": "Broken Lamp Post",  "desc": "Lamp post on Al-Najah Street is out for 3 nights", "lat": 31.901, "lng": 35.202, "district": "dist_3", "citizen_idx": 0},
    {"category": "waste",        "sub": "Overflowing Bin",   "desc": "Garbage bin near central market is overflowing",    "lat": 31.894, "lng": 35.196, "district": "dist_1", "citizen_idx": 1},
    {"category": "traffic",      "sub": "Pothole",           "desc": "Deep pothole on main road causing accidents",        "lat": 31.909, "lng": 35.209, "district": "dist_2", "citizen_idx": 2},
    {"category": "water",        "sub": "Water Leak",        "desc": "Water pipe leaking near the roundabout",            "lat": 31.924, "lng": 35.219, "district": "dist_4", "citizen_idx": 3},
    {"category": "infrastructure","sub": "Broken Bench",     "desc": "Park bench is broken and dangerous",                "lat": 31.879, "lng": 35.184, "district": "dist_5", "citizen_idx": 4},
    {"category": "waste",        "sub": "Illegal Dumping",   "desc": "Large pile of illegal waste dumped on side road",   "lat": 31.900, "lng": 35.200, "district": "dist_3", "citizen_idx": 0},
    {"category": "lighting",     "sub": "Unlit Zone",        "desc": "Entire street section has no lighting at night",    "lat": 31.893, "lng": 35.195, "district": "dist_1", "citizen_idx": 1},
    {"category": "traffic",      "sub": "Signal Failure",    "desc": "Traffic lights at main junction are not working",   "lat": 31.912, "lng": 35.212, "district": "dist_2", "citizen_idx": 2},
]


def seed_all():
    print("\n🌱 Seeding all databases...\n")

    # 1. Init schemas
    mongo.init_mongo()
    neo4j.init_neo4j()
    neo4j.seed_static_nodes()

    try:
        cass.init_cassandra()
    except Exception as e:
        print(f"⚠️  Cassandra init skipped (may not be ready): {e}")

    # 2. Seed citizens
    citizen_ids = []
    for c in CITIZENS:
        uid = mongo.create_user(
            name=c["name"], email=c["email"],
            national_id=c["national_id"], phone=c["phone"],
            district_id=c["district"], lat=c["lat"], lng=c["lng"]
        )
        if uid is None:
            # Already exists — fetch it
            existing = mongo.get_user_by_email(c["email"])
            uid = existing["_id"]

        citizen_ids.append(uid)

        # Create Neo4j citizen node
        neo4j.create_citizen_node(uid, c["name"], c["district"])

        # Warm Redis leaderboard
        redis_c.update_leaderboard(uid, 0)

        print(f"  👤 Citizen: {c['name']} → {uid}")

    # 3. Seed requests
    request_ids = []
    for req in REQUESTS:
        cid = citizen_ids[req["citizen_idx"]]
        rid = mongo.create_request(
            citizen_id=cid,
            category=req["category"],
            subcategory=req["sub"],
            description=req["desc"],
            lat=req["lat"], lng=req["lng"],
            district_id=req["district"]
        )
        request_ids.append(rid)

        # MongoDB dept mapping
        dept_map = {
            "waste": "dept_sanitation", "lighting": "dept_lighting",
            "traffic": "dept_traffic",  "water": "dept_utilities",
            "infrastructure": "dept_public_works", "emergency": "dept_emergency"
        }
        dept_id = dept_map.get(req["category"], "dept_public_works")

        # Neo4j request node + edges
        neo4j.create_request_node(rid, req["category"], "OPEN", cid, dept_id)
        neo4j.link_request_to_district(rid, req["district"])

        # Redis — cache status + push to user recent
        redis_c.cache_request_status(rid, "OPEN")
        redis_c.push_recent_request(cid, rid)

        # Cassandra event log
        try:
            cass.log_status_change(
                request_id=rid, citizen_id=cid,
                district_id=req["district"], category=req["category"],
                old_status="", new_status="OPEN", actor=cid,
                comment="Request submitted"
            )
        except Exception:
            pass

        print(f"  📋 Request: [{req['category']}] {req['sub']} → {rid}")

    # 4. Simulate resolutions
    if request_ids:
        rid = request_ids[0]
        cid = citizen_ids[0]
        mongo.update_request_status(rid, "RESOLVED", "tech_1", "Lamp replaced successfully")
        neo4j.mark_request_resolved(rid, "tech_1")
        redis_c.invalidate_request_status(rid)
        redis_c.cache_request_status(rid, "RESOLVED")
        mongo.update_civic_score(cid, 5)
        redis_c.update_leaderboard(cid, 5)
        print(f"\n  ✅ Simulated resolution for request {rid}")

    # Simulate more resolutions for richer graph queries
    extra_resolutions = [
        (1, "tech_2"),  # request index 1 resolved by tech_2
        (2, "tech_3"),  # request index 2 resolved by tech_3
        (4, "tech_4"),  # request index 4 resolved by tech_4
        (6, "tech_1"),  # request index 6 resolved by tech_1 (2nd for tech_1)
    ]
    for idx, tech in extra_resolutions:
        if idx < len(request_ids):
            rid = request_ids[idx]
            cid = citizen_ids[min(idx, len(citizen_ids) - 1)]
            try:
                mongo.update_request_status(rid, "RESOLVED", tech, "Issue resolved")
            except Exception:
                pass
            neo4j.mark_request_resolved(rid, tech)
            redis_c.invalidate_request_status(rid)
            redis_c.cache_request_status(rid, "RESOLVED")
            print(f"  ✅ Simulated resolution: request {rid} by {tech}")

    # Warm category cache
    redis_c.get_category_list()

    print("\n✅ All databases seeded successfully!\n")
    print("  MongoDB  → users, requests")
    print("  Neo4j    → citizen/dept/district nodes + edges")
    print("  Redis    → sessions, status cache, leaderboard")
    print("  Cassandra→ event_log\n")


if __name__ == "__main__":
    seed_all()
