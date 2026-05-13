"""
Redis Client — Sessions, Caching, Dashboard Counters
Member responsible: Ahmad

Cache key patterns:
  session:{token}              → user_id + role          TTL: 30 min
  req:status:{req_id}          → status string           TTL: 60 sec
  dashboard:dept:{dept_id}     → JSON summary            TTL: 5 min
  hotspot:district:{zone_id}   → top issue locations     TTL: 10 min
  user:recent:{user_id}        → list of last 5 req IDs  TTL: 1 hour
  category:list                → full category tree      TTL: 24 hours
"""

import os
import json
import uuid
import redis

# TTLs in seconds
TTL_SESSION         = 1800    # 30 min
TTL_REQ_STATUS      = 60      # 1 min
TTL_DEPT_DASHBOARD  = 300     # 5 min
TTL_HOTSPOT         = 600     # 10 min
TTL_USER_RECENT     = 3600    # 1 hour
TTL_CATEGORY_LIST   = 86400   # 24 hours


def get_redis():
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", 6379))
    return redis.Redis(host=host, port=port, decode_responses=True)


def ping():
    try:
        get_redis().ping()
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────
# SESSION MANAGEMENT
# ─────────────────────────────────────────────

def create_session(user_id, role="citizen"):
    """Create a new session token and store in Redis."""
    r = get_redis()
    token = str(uuid.uuid4())
    payload = json.dumps({"user_id": user_id, "role": role})
    r.setex(f"session:{token}", TTL_SESSION, payload)
    return token


def get_session(token):
    """Return session data dict or None if expired/missing."""
    r = get_redis()
    data = r.get(f"session:{token}")
    if data:
        r.expire(f"session:{token}", TTL_SESSION)   # sliding window
        return json.loads(data)
    return None


def delete_session(token):
    """Logout — delete the session key."""
    r = get_redis()
    r.delete(f"session:{token}")


# ─────────────────────────────────────────────
# REQUEST STATUS CACHE
# ─────────────────────────────────────────────

def cache_request_status(request_id, status):
    r = get_redis()
    r.setex(f"req:status:{request_id}", TTL_REQ_STATUS, status)


def get_cached_status(request_id):
    r = get_redis()
    return r.get(f"req:status:{request_id}")


def invalidate_request_status(request_id):
    """Call this whenever a request status changes in MongoDB."""
    r = get_redis()
    r.delete(f"req:status:{request_id}")


# ─────────────────────────────────────────────
# DEPARTMENT DASHBOARD COUNTERS
# ─────────────────────────────────────────────

def cache_dept_dashboard(dept_id, summary_dict):
    r = get_redis()
    r.setex(f"dashboard:dept:{dept_id}", TTL_DEPT_DASHBOARD, json.dumps(summary_dict))


def get_dept_dashboard(dept_id):
    r = get_redis()
    data = r.get(f"dashboard:dept:{dept_id}")
    return json.loads(data) if data else None


def invalidate_dept_dashboard(dept_id):
    r = get_redis()
    r.delete(f"dashboard:dept:{dept_id}")


# ─────────────────────────────────────────────
# HOTSPOT CACHE (per district)
# ─────────────────────────────────────────────

def cache_hotspot(district_id, locations_list):
    r = get_redis()
    r.setex(f"hotspot:district:{district_id}", TTL_HOTSPOT, json.dumps(locations_list))


def get_hotspot(district_id):
    r = get_redis()
    data = r.get(f"hotspot:district:{district_id}")
    return json.loads(data) if data else None


# ─────────────────────────────────────────────
# USER RECENT ACTIVITY (list)
# ─────────────────────────────────────────────

def push_recent_request(user_id, request_id):
    """Keep a capped list of last 5 request IDs for a user."""
    r = get_redis()
    key = f"user:recent:{user_id}"
    r.lpush(key, request_id)
    r.ltrim(key, 0, 4)       # keep only latest 5
    r.expire(key, TTL_USER_RECENT)


def get_recent_requests(user_id):
    r = get_redis()
    return r.lrange(f"user:recent:{user_id}", 0, -1)


# ─────────────────────────────────────────────
# CATEGORY LIST (rarely changes)
# ─────────────────────────────────────────────

CATEGORY_TREE = {
    "waste":        ["Overflowing Bin", "Illegal Dumping", "Blocked Drainage"],
    "lighting":     ["Broken Lamp Post", "Unlit Zone", "Flickering Light"],
    "traffic":      ["Pothole", "Road Closure", "Signal Failure", "Congestion"],
    "infrastructure": ["Broken Bench", "Damaged Sidewalk", "Graffiti"],
    "water":        ["Water Leak", "Sewage Issue"],
    "emergency":    ["Flooding", "Fire", "Public Hazard"],
}


def get_category_list():
    r = get_redis()
    cached = r.get("category:list")
    if cached:
        return json.loads(cached)
    # Warm the cache
    r.setex("category:list", TTL_CATEGORY_LIST, json.dumps(CATEGORY_TREE))
    return CATEGORY_TREE


# ─────────────────────────────────────────────
# SORTED SET — LEADERBOARD (Civic Score)
# ─────────────────────────────────────────────

def update_leaderboard(user_id, score):
    r = get_redis()
    r.zadd("leaderboard:civic_score", {user_id: score})


def get_top_citizens(limit=10):
    r = get_redis()
    return r.zrevrange("leaderboard:civic_score", 0, limit - 1, withscores=True)


# ─────────────────────────────────────────────
# DEBUG HELPERS
# ─────────────────────────────────────────────

def get_all_cache_keys():
    r = get_redis()
    return r.keys("*")


def get_redis_info():
    r = get_redis()
    info = r.info("memory")
    return {
        "used_memory_human": info.get("used_memory_human"),
        "total_keys":        r.dbsize(),
        "connected":         True
    }
