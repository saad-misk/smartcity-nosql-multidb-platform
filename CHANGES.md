# Changes — Stabilisation Pass

Summary of fixes applied on top of the original `smartcity-nosql-multidb-platform`.
Nothing was restructured; every change is in place. Same file layout, same project,
just unbroken.

---

## Backend — Routes & DB Clients

### `routes/requests.py` (rewritten)
The routes called functions that didn't exist in the db clients. Fixed:
- `es.search_similar_requests(...)` → `es.search_similar(...)` (real name, real signature, no `sub_category` arg)
- `mongo.update_civic_score(...)` → `mongo.increment_civic_score(...)`
- `mongo.create_service_request(..., photo_urls=, similarity_score=, similar_request_ids=)` → removed the three params the function doesn't accept
- `neo4j.create_request_node(rid, cat, "pending", cid, did)` → `(rid, cat, cid, did)` (real arity is 4)
- Replaced deprecated `datetime.utcnow()` with `datetime.now(timezone.utc)`

### `routes/analytics.py`
- `redis_c.get_redis_info()` → `redis_c.get_info()`
- `mongo.analytics_avg_response_time()` → `mongo.analytics_avg_resolution_time()`

### `routes/graph.py` (rewritten)
Removed six endpoints that called nonexistent Cypher functions:
- `query_dept_technicians`, `query_shared_area_departments`, `query_cross_area_reporters`,
  `query_citizen_journey`, `query_area_connectivity`, `query_variable_length_path`

Kept and grouped (Basic / Intermediate / Advanced / Visual) the nine endpoints that
are actually backed by working Cypher in `db/neo4j_client.py`.

### `seed/seed_all.py`
- `mongo.init_mongo()` → `mongo.init_indexes()`
- `neo4j.init_neo4j()` → `neo4j.init_constraints()`
- `neo4j.create_request_node(rid, cat, "pending", cid, did)` → `(rid, cat, cid, did)`
- Replaced deprecated `datetime.utcnow()`
- Added technician login accounts (`tech_1@smartcity.local` ... `tech_5@smartcity.local`)
  so the `/dashboard` flow can be demoed without manual user creation.
- Added two manager login accounts (`saad@example.com`, `manager@example.com`)
  so the `/analytics` flow can be demoed.
- All seeded users use password `demo`.

### `app.py`
- Added `GET /analytics` route (was missing — managers were redirected there but
  the route didn't exist).

---

## Frontend

### `templates/graph.html` (new)
Was referenced by `app.py` and the README but didn't exist. Added a minimal
graph-explorer page that calls the Neo4j endpoints.

### `templates/index.html`
- Registration form: "Area ID" + "Area Name" text inputs replaced with a single
  `<select>` populated from the 8 seeded districts. A citizen no longer has to
  guess what to type.

### `templates/submit.html`
- Hardcoded category options (`Roads`, `Sanitation`, `Parks`, ...) were wrong —
  the backend uses `waste`, `lighting`, `traffic`, etc. Category dropdown is now
  empty in HTML and filled at runtime from `GET /api/categories`.
- Sub-category is now a `<select>` that updates when the category changes.
- Area is a `<select>` populated by JS.

### `static/js/app.js` (rewritten)
Most fields the JS read didn't exist on the API responses. Fixed end-to-end:
- `data.totalRequests` → `data.total_requests` (and the rest of the snake_case map)
- `issue._id` → `issue.category`, `area._id` → `area.areaName`, `dept._id` → `dept.department`
- `data.nodeCount` / `data.relationshipCount` → `data.nodes` (object) / `data.relationships`
- Added `loadCategoriesIntoForm()` so the submit page fetches `/api/categories`
- Added `loadGraphExplorer()` for the new graph page
- Added `statusClass()` helper so `in_progress` maps to the `.badge-in-progress` CSS class

### `static/css/style.css`
No changes — existing classes covered every status/priority once the JS normalised
the status string.

---

## Docs

### `models.md`
Was a single unreadable line. Re-formatted as proper markdown with one block per
collection.

### `README.md`
Rewritten to match what the project actually does. Removed promises of endpoints
that weren't implemented; added the demo accounts seeded by `seed_all.py`; added
the team's CAP trade-off table.

### Line endings
Normalised CRLF → LF on `Dockerfile`, `docker-compose.yml`, `requirements.txt`,
`models.md`.

---

## Verification

- All 11 Python files compile clean (`python -m py_compile`).
- All function references between `routes/` and `db/` resolve — checked with a
  static `hasattr` scan over every called name.
- Flask app boots and registers all 33 routes without runtime import errors.

## What this pass deliberately did NOT do

- No new libraries.
- No React, no Vue, no build step.
- No schema changes in MongoDB / Neo4j / Redis / Elasticsearch.
- No changes to the four db client files (`db/*.py`) — they were the source of
  truth for function names. Routes were brought in line with them, not the other
  way round.
- No file moved or renamed. The GitHub structure is identical.
