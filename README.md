# SmartCity NoSQL Platform

A minimal multi-database demo for a Smart City Services Management System.

## Databases Used

| Database       | Role                                  |
|----------------|---------------------------------------|
| MongoDB        | Primary data store (users, citizens, requests) |
| Neo4j          | Urban relationship graph (areas, departments, technicians) |
| Redis          | Sessions, caching, leaderboard         |
| Elasticsearch  | Similarity search for incoming requests |

---

## Quick Start (Docker — Recommended)

### 1. Start all services
```bash
docker-compose up --build
```

### 2. Seed the databases
Open a second terminal:
```bash
docker exec -it smartcity_app python seed/seed_all.py
```

### 3. Open the app
- Main App: http://localhost:5000
- Dashboard: http://localhost:5000/dashboard
- Neo4j Browser: http://localhost:7474 (user: neo4j, password: smartcity123)

---

## Local Development (without Docker)

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Start databases manually
Make sure MongoDB, Neo4j, Redis, and Elasticsearch are running locally with default ports.

### 3. Set environment variables
```bash
export MONGO_URI=mongodb://localhost:27017/smartcity
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=smartcity123
export REDIS_HOST=localhost
export REDIS_PORT=6379
export ELASTICSEARCH_URL=http://localhost:9200
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
├── app.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── db/
│   ├── mongo_client.py
│   ├── neo4j_client.py
│   ├── redis_client.py
│   └── elasticsearch_client.py
├── routes/
│   ├── citizens.py
│   ├── requests.py
│   ├── analytics.py
│   └── graph.py
├── templates/
│   ├── index.html
│   ├── dashboard.html
│   ├── submit.html
│   └── graph.html
└── seed/
    └── seed_all.py
```

---

## Minimal Demo Endpoints (two per DB)

### MongoDB (Aggregation)
- GET /api/analytics/top-issues
- GET /api/analytics/by-area

### Neo4j (Graph)
- GET /api/graph/department-coverage
- GET /api/graph/top-technicians

### Redis (Cache + Leaderboard)
- GET /api/analytics/leaderboard
- GET /api/analytics/overview (includes Redis stats)

### Elasticsearch (Similarity Search)
- GET /api/search/similar?q=broken%20light
- POST /api/requests (similarity boost before storing)

---

## Demo Flow (Presentation)

1. Open http://localhost:5000 and login with ahmed@example.com.
2. Dashboard: show Top Issues and Requests by Area (MongoDB) + Leaderboard (Redis).
3. Search Similar Requests (Elasticsearch) using the dashboard search box.
4. Submit a new request to show similarity boosting + storage flow.
5. Graph Explorer: run Department Coverage and Top Technicians (Neo4j).
