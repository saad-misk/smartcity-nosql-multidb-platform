# 🏙️ SmartCity NoSQL Platform

A multi-database NoSQL prototype for a Smart City Services Management System.

## Databases Used

| Database   | Role                        | Member     |
|------------|-----------------------------|------------|
| MongoDB    | Citizen profiles, requests, geospatial queries, analytics | Haitham |
| Neo4j      | Urban relationship graph    | Saad       |
| Redis      | Sessions, caching, leaderboard | Ahmad   |
| Cassandra  | Event log (time-series)     | Moheeb     |

---

## Quick Start (Docker — Recommended)

### 1. Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running

### 2. Clone / Download the project
```bash
cd smartcity/
```

### 3. Start all services
```bash
docker-compose up --build
```
This starts: MongoDB, Neo4j, Redis, Cassandra, and the Flask app.

### 4. Seed the databases
Open a second terminal:
```bash
docker exec -it smartcity_app python seed/seed_all.py
```

### 5. Open the app
- **Main App:** http://localhost:5000
- **Dashboard:** http://localhost:5000/dashboard
- **Neo4j Browser:** http://localhost:7474 (user: `neo4j`, password: `smartcity123`)

---

## Local Development (without Docker)

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Start databases manually
Make sure MongoDB, Neo4j, Redis, and Cassandra are running locally with default ports.

### 3. Set environment variables
```bash
export MONGO_URI=mongodb://localhost:27017/smartcity
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=smartcity123
export REDIS_HOST=localhost
export CASSANDRA_HOST=localhost
```

### 4. Seed and run
```bash
python seed/seed_all.py
python app.py
```

---

## Project Structure

```
smartcity/
├── app.py                   # Flask entry point
├── docker-compose.yml       # All 4 databases + app
├── Dockerfile
├── requirements.txt
├── db/
│   ├── mongo_client.py      # MongoDB CRUD + aggregation + geospatial
│   ├── neo4j_client.py      # Graph schema + Cypher queries
│   ├── redis_client.py      # Sessions + caching layer
│   └── cassandra_client.py  # Event log (wide-column)
├── routes/
│   ├── citizens.py          # Register, login, logout
│   ├── requests.py          # Submit, track, update status
│   ├── analytics.py         # Aggregation dashboards
│   └── graph.py             # Graph query API
├── templates/
│   ├── index.html           # Login + Register
│   ├── dashboard.html       # Analytics dashboard
│   ├── submit.html          # Report an issue
│   └── graph.html           # Neo4j graph explorer
└── seed/
    └── seed_all.py          # Populate all 4 databases
```

---

## Key API Endpoints

### Citizens
| Method | Endpoint         | Description              |
|--------|-----------------|--------------------------|
| POST   | /api/register    | Register a new citizen   |
| POST   | /api/login       | Login (creates Redis session) |
| POST   | /api/logout      | Logout (deletes session) |
| GET    | /api/me          | Get current user profile |

### Service Requests
| Method | Endpoint                        | Description                     |
|--------|---------------------------------|---------------------------------|
| POST   | /api/requests                   | Submit a new request (multi-DB) |
| GET    | /api/requests/<id>              | Get request (Redis cache-first) |
| PATCH  | /api/requests/<id>/status       | Update status + invalidate cache|
| GET    | /api/my-requests                | Citizen's own requests          |
| GET    | /api/requests/nearby?lat=&lng=  | Geospatial search (MongoDB)     |
| GET    | /api/categories                 | Category list (Redis cached)    |

### Analytics (MongoDB Aggregation)
| Method | Endpoint                        | Description                  |
|--------|---------------------------------|------------------------------|
| GET    | /api/analytics/overview         | KPI stats                    |
| GET    | /api/analytics/top-issues       | Most reported categories     |
| GET    | /api/analytics/by-district      | Requests per district        |
| GET    | /api/analytics/response-time    | Avg resolution time per dept |
| GET    | /api/analytics/cassandra/events | Event log from Cassandra     |
| GET    | /api/analytics/leaderboard      | Civic score (Redis sorted set)|

### Graph (Neo4j) — 13 Endpoints

**Basic (Category A)**
| Method | Endpoint                              | Description                  |
|--------|---------------------------------------|------------------------------|
| GET    | /api/graph/stats                      | Node + relationship counts   |
| GET    | /api/graph/department-coverage        | Dept → district coverage map |
| GET    | /api/graph/top-technicians            | Technician performance       |
| GET    | /api/graph/department/&lt;id&gt;/technicians| Dept technician list     |
| GET    | /api/graph/citizen-journey?name=      | Full citizen interaction chain|

**Intermediate (Category B)**
| Method | Endpoint                              | Description                  |
|--------|---------------------------------------|------------------------------|
| GET    | /api/graph/shared-districts           | Depts sharing a district     |
| GET    | /api/graph/cross-district-reporters   | Citizens outside home district|
| GET    | /api/graph/district-workload          | Districts by open issues     |
| GET    | /api/graph/department-efficiency      | Resolution rate per dept     |

**Advanced / Graph-Only (Category C)**
| Method | Endpoint                              | Description                  |
|--------|---------------------------------------|------------------------------|
| GET    | /api/graph/shortest-path?from=&to=    | shortestPath algorithm       |
| GET    | /api/graph/impact-analysis?department=| Cascade impact analysis      |
| GET    | /api/graph/collaboration-gaps         | Missing collaboration links  |
| GET    | /api/graph/district-connectivity      | District health score        |
| GET    | /api/graph/explore-district?name=     | Variable-length path scan    |
| GET    | /api/graph/visual                     | Full graph for vis.js render |

---

## Demo Flow (for Presentation)

1. **Open** http://localhost:5000
2. **Login** with `ahmed@example.com`
3. **Navigate** to Dashboard — show KPIs + MongoDB aggregation results
4. **Submit** a new waste complaint — explain the 4-DB write flow
5. **Open** Graph Explorer — run "Departments Sharing Districts" Cypher query
6. **Show** http://localhost:7474 Neo4j browser for visual graph

---

## CAP Theorem Alignment

| System    | CAP  | Implication                             |
|-----------|------|-----------------------------------------|
| MongoDB   | CP   | Consistent profiles; brief write unavailability acceptable |
| Neo4j     | CP   | Relationship integrity critical          |
| Redis     | AP   | Slightly stale cache OK; availability > consistency |
| Cassandra | AP   | High write availability; eventual consistency OK |
