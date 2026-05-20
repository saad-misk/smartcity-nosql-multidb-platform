"""
Redis Client — SmartCity
Handles: Sessions, request-status cache, department dashboard cache,
         user recent-activity list, category tree, civic-score leaderboard.

Key patterns:
  session:{token}          → user payload JSON      TTL: 30 min
  req:status:{req_id}      → status string          TTL:  1 min
  dashboard:dept:{dept_id} → summary JSON           TTL:  5 min
  user:recent:{user_id}    → list of last-5 req IDs TTL:  1 hour
  category:list            → full category JSON      TTL: 24 hours
  leaderboard:civic_score  → sorted set (score)      no TTL
"""

import os, json, uuid
import redis

TTL_SESSION    = 1800   # 30 min
TTL_STATUS     = 60     # 1 min
TTL_DASHBOARD  = 300    # 5 min
TTL_RECENT     = 3600   # 1 hour
TTL_CATEGORIES = 86400  # 24 hours

CATEGORY_TREE = {
    "waste":          ["Overflowing Bin", "Illegal Dumping", "Blocked Drainage"],
    "lighting":       ["Broken Lamp Post", "Unlit Zone", "Flickering Light"],
    "traffic":        ["Pothole", "Road Closure", "Signal Failure"],
    "infrastructure": ["Broken Bench", "Damaged Sidewalk", "Graffiti"],
    "water":          ["Water Leak", "Sewage Issue"],
    "emergency":      ["Flooding", "Fire", "Public Hazard"],
}


def get_redis():
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True,
    )


def ping():
    try:
        get_redis().ping()
        return True
    except Exception:
        return False


# ── Sessions ──────────────────────────────────────────────────────────────────

def create_session(user_id, role="citizen", citizen_id=None,
                   technician_id=None, username=None):
    r = get_redis()
    token = str(uuid.uuid4())
    payload = {
        "user_id": user_id,
        "role": role,
        "citizen_id": citizen_id,
        "technician_id": technician_id,
        "username": username,
    }
    r.setex(f"session:{token}", TTL_SESSION, json.dumps(payload))
    return token


def get_session(token):
    r = get_redis()
    data = r.get(f"session:{token}")
    if data:
        r.expire(f"session:{token}", TTL_SESSION)   # sliding window
        return json.loads(data)
    return None


def delete_session(token):
    get_redis().delete(f"session:{token}")


# ── Request-status cache ──────────────────────────────────────────────────────

def cache_request_status(req_id, status):
    get_redis().setex(f"req:status:{req_id}", TTL_STATUS, status)


def get_cached_status(req_id):
    return get_redis().get(f"req:status:{req_id}")


def invalidate_request_status(req_id):
    get_redis().delete(f"req:status:{req_id}")


# ── Department dashboard cache ────────────────────────────────────────────────

def cache_dept_dashboard(dept_id, summary):
    get_redis().setex(f"dashboard:dept:{dept_id}", TTL_DASHBOARD, json.dumps(summary))


def get_dept_dashboard(dept_id):
    data = get_redis().get(f"dashboard:dept:{dept_id}")
    return json.loads(data) if data else None


def invalidate_dept_dashboard(dept_id):
    get_redis().delete(f"dashboard:dept:{dept_id}")


# ── User recent requests (capped list of 5) ───────────────────────────────────

def push_recent_request(user_id, req_id):
    r = get_redis()
    key = f"user:recent:{user_id}"
    r.lpush(key, req_id)
    r.ltrim(key, 0, 4)          # keep only latest 5
    r.expire(key, TTL_RECENT)


def get_recent_requests(user_id):
    return get_redis().lrange(f"user:recent:{user_id}", 0, -1)


# ── Category tree (rarely changes) ───────────────────────────────────────────

def get_category_list():
    r = get_redis()
    cached = r.get("category:list")
    if cached:
        return json.loads(cached)
    r.setex("category:list", TTL_CATEGORIES, json.dumps(CATEGORY_TREE))
    return CATEGORY_TREE


# ── Civic-score leaderboard (sorted set) ─────────────────────────────────────

def update_leaderboard(user_id, score):
    get_redis().zadd("leaderboard:civic_score", {user_id: score})


def get_top_citizens(limit=10):
    return get_redis().zrevrange(
        "leaderboard:civic_score", 0, limit - 1, withscores=True
    )


# ── Health info ───────────────────────────────────────────────────────────────

def get_info():
    r = get_redis()
    mem = r.info("memory")
    return {
        "used_memory_human": mem.get("used_memory_human"),
        "total_keys": r.dbsize(),
        "connected": True,
    }