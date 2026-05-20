# SmartCity NoSQL Platform

A multi-database Smart City Services demo built with Python (Flask) and four
NoSQL stores. Each database is used where it actually fits:

| Database       | Role                                                       | Owner   |
|----------------|------------------------------------------------------------|---------|
| MongoDB        | Primary store: users, citizens, service requests, ref data | Haitham |
| Neo4j          | Urban relationship graph (areas, depts, technicians)       | Saad    |
| Redis          | Sessions, status cache, recent lists, civic leaderboard    | Ahmad   |
| Elasticsearch  | Similarity search on incoming requests                     | Moheeb  |

---

## Project Structure

```
smartcity-nosql-multidb-platform/
├── app.py                  # Flask entry point
├── docker-compose.yml      # Spins up all 4 databases + the app
├── Dockerfile
├── requirements.txt
├── models.md               # Document shapes (Mongo collections)
│
├── db/
│   ├── mongo_client.py         # Mongo CRUD + aggregations
│   ├── neo4j_client.py         # Cypher queries + graph seed
│   ├── redis_client.py         # Session, cache, leaderboard
│   └── elasticsearch_client.py # Similarity search
│
├── routes/
│   ├── citizens.py     # /api/register, /api/login, /api/logout, /api/me
│   ├── requests.py     # Submit / track / update service requests
│   ├── analytics.py    # Aggregation pipeline reports
│   └── graph.py        # Cypher endpoints
│
├── templates/          # Plain HTML, server-rendered
│   ├── index.html      # Login + Register
│   ├── submit.html     # Citizen: submit a request
│   ├── dashboard.html  # Technician: manage incoming
│   ├── analytics.html  # Manager: city-wide stats
│   └── graph.html      # Graph explorer (Neo4j)
│
├── static/             # Plain CSS + plain JS, no frameworks
│   ├── css/style.css
│   └── js/app.js
│
└── seed/
    └── seed_all.py     # Populates all 4 databases
```

---

## Quick Start (Docker — recommended)

```bash
# 1. Start everything
docker-compose up --build

# 2. In a second terminal, seed the databases
docker exec -it smartcity_app python seed/seed_all.py
```

Then open:

| Page              | URL                              |
|-------------------|----------------------------------|
| Login / Register  | http://localhost:5000            |
| Citizen submit    | http://localhost:5000/submit     |
| Technician panel  | http://localhost:5000/dashboard  |
| City analytics    | http://localhost:5000/analytics  |
| Graph explorer    | http://localhost:5000/graph      |
| Health check      | http://localhost:5000/health     |
| Neo4j browser     | http://localhost:7474            |

Default Neo4j login: `neo4j` / `smartcity123`.

Demo accounts (created by `seed_all.py`, all use password `demo`):

| Email                       | Role        |
|-----------------------------|-------------|
| ahmed@example.com           | citizen     |
| fatima@example.com          | citizen     |
| omar@example.com            | citizen     |
| layla@example.com           | citizen     |
| yusuf@example.com           | citizen     |
| tech_1@smartcity.local      | technician  |
| tech_2@smartcity.local      | technician  |
| tech_3@smartcity.local      | technician  |
| tech_4@smartcity.local      | technician  |
| tech_5@smartcity.local      | technician  |
| saad@example.com            | manager     |
| manager@example.com         | manager     |

---

## Local Development (no Docker)

```bash
pip install -r requirements.txt

# Make sure MongoDB, Neo4j, Redis, Elasticsearch are running locally
# (default ports). Then export connection settings if they differ:

export MONGO_URI=mongodb://localhost:27017/smartcity
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=smartcity123
export REDIS_HOST=localhost
export REDIS_PORT=6379
export ELASTICSEARCH_URL=http://localhost:9200

python seed/seed_all.py
python app.py
```

---

## Key API Endpoints

### Auth (MongoDB + Redis)
- `POST /api/register`        — create a citizen account
- `POST /api/login`           — returns a session token
- `POST /api/logout`
- `GET  /api/me`

### Service Requests (Mongo + Neo4j + Redis + Elasticsearch)
- `POST  /api/requests`                  — submit (full multi-DB flow)
- `GET   /api/requests/<id>`             — cache-first read
- `GET   /api/my-requests`               — citizen's own list
- `PATCH /api/requests/<id>/status`      — technician updates status
- `GET   /api/requests/nearby?lat=&lng=` — geospatial (Mongo $near)
- `GET   /api/categories`                — Redis-cached category tree

### Search (Elasticsearch)
- `GET /api/search/similar?q=...`        — fuzzy + scored

### Analytics (MongoDB aggregation + Redis)
- `GET /api/analytics/overview`
- `GET /api/analytics/top-issues?days=30&limit=5`
- `GET /api/analytics/by-area?days=30`
- `GET /api/analytics/response-time`
- `GET /api/analytics/leaderboard`

### Graph (Neo4j)
- `GET /api/graph/stats`
- `GET /api/graph/department-coverage`
- `GET /api/graph/area-workload`
- `GET /api/graph/department-efficiency`
- `GET /api/graph/top-technicians?limit=5`
- `GET /api/graph/shortest-path?from=&to=`
- `GET /api/graph/impact-analysis?department=`
- `GET /api/graph/collaboration-gaps`
- `GET /api/graph/visual?limit=150`

---

## Demo Flow (presentation)

1. **Login** at `/` as `ahmed@example.com` / `demo`.
2. **Submit** a new request at `/submit` — pick a category that's already
   common (e.g. `lighting` / Broken Lamp Post). Watch the similarity boost
   the priority, and notice the response includes a similarity score.
3. **Logout**, login as a manager (you'll need to add one to the seed)
   and open `/analytics` — top issues, breakdown by area, response time,
   and the civic-score leaderboard all light up.
4. Open `/graph` — Neo4j shows department coverage, area workload, and
   the collaboration-gaps query, which is something only a graph DB can
   answer cleanly.

---

## CAP Trade-offs per Database

- **MongoDB** — CP. Flexible schema + 2dsphere geospatial. Primary store.
- **Redis**   — AP. We accept stale-cache risk for speed; TTLs cap drift.
- **Neo4j**   — CP. Graph integrity matters more than write throughput.
- **Elastic** — AP. Eventual consistency is fine for similarity search.
