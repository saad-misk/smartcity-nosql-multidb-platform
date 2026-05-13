"""
Cassandra Client — Append-only Event Log for Status Changes
Member responsible: Moheeb

Table: event_log
  Partition key: (district_id, date)   ← fast range scans per district per day
  Clustering key: event_time DESC      ← newest events first

This demonstrates the wide-column store pattern for time-series / audit logging.
"""

import os
import uuid
from datetime import datetime, timezone, date
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider


def get_session():
    host = os.getenv("CASSANDRA_HOST", "localhost")
    cluster = Cluster([host])
    session = cluster.connect()
    return session


def init_cassandra():
    """Create keyspace and table."""
    session = get_session()

    session.execute("""
        CREATE KEYSPACE IF NOT EXISTS smartcity
        WITH replication = {
            'class': 'SimpleStrategy',
            'replication_factor': 1
        }
    """)

    session.set_keyspace("smartcity")

    # Event log — partitioned by district + date for efficient range scans
    session.execute("""
        CREATE TABLE IF NOT EXISTS event_log (
            district_id  TEXT,
            event_date   DATE,
            event_time   TIMESTAMP,
            event_id     UUID,
            request_id   TEXT,
            citizen_id   TEXT,
            category     TEXT,
            old_status   TEXT,
            new_status   TEXT,
            actor        TEXT,
            comment      TEXT,
            PRIMARY KEY ((district_id, event_date), event_time, event_id)
        ) WITH CLUSTERING ORDER BY (event_time DESC)
    """)

    # Aggregated daily stats per district (materialized summary)
    session.execute("""
        CREATE TABLE IF NOT EXISTS daily_stats (
            district_id   TEXT,
            stat_date     DATE,
            total_open    COUNTER,
            total_resolved COUNTER,
            PRIMARY KEY (district_id, stat_date)
        )
    """)

    print("✅ Cassandra keyspace and tables created.")


# ─────────────────────────────────────────────
# LOG AN EVENT
# ─────────────────────────────────────────────

def log_status_change(request_id, citizen_id, district_id,
                      category, old_status, new_status, actor, comment=""):
    """Append a status-change event to the log."""
    session = get_session()
    session.set_keyspace("smartcity")

    now = datetime.now(timezone.utc)

    session.execute("""
        INSERT INTO event_log (
            district_id, event_date, event_time, event_id,
            request_id, citizen_id, category,
            old_status, new_status, actor, comment
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        district_id,
        now.date(),
        now,
        uuid.uuid4(),
        request_id, citizen_id, category,
        old_status, new_status, actor, comment
    ))

    # Update daily counter
    if new_status == "OPEN":
        session.execute(
            "UPDATE daily_stats SET total_open = total_open + 1 "
            "WHERE district_id=%s AND stat_date=%s",
            (district_id, now.date())
        )
    elif new_status == "RESOLVED":
        session.execute(
            "UPDATE daily_stats SET total_resolved = total_resolved + 1 "
            "WHERE district_id=%s AND stat_date=%s",
            (district_id, now.date())
        )



# ─────────────────────────────────────────────
# QUERY EVENTS
# ─────────────────────────────────────────────

def get_events_for_district_today(district_id):
    """Fetch all events for a district today."""
    session = get_session()
    session.set_keyspace("smartcity")

    today = date.today()
    rows = session.execute(
        "SELECT * FROM event_log WHERE district_id=%s AND event_date=%s",
        (district_id, today)
    )
    results = [dict(r._asdict()) for r in rows]
    return results


def get_daily_stats(district_id, days=7):
    """Return daily open/resolved counts for last N days."""
    from datetime import timedelta
    session = get_session()
    session.set_keyspace("smartcity")

    today = date.today()
    dates = [today - timedelta(days=i) for i in range(days)]

    results = []
    for d in dates:
        row = session.execute(
            "SELECT * FROM daily_stats WHERE district_id=%s AND stat_date=%s",
            (district_id, d)
        ).one()
        if row:
            results.append({
                "date":     str(d),
                "open":     row.total_open,
                "resolved": row.total_resolved
            })
    return results


def get_recent_events(district_id, limit=20):
    from datetime import timedelta
    session = get_session()
    session.set_keyspace("smartcity")
    results = []
    for i in range(3):  # check last 3 days
        day = date.today() - timedelta(days=i)
        rows = session.execute(
            "SELECT * FROM event_log WHERE district_id=%s AND event_date=%s LIMIT %s",
            (district_id, day, limit)
        )
        results.extend([dict(r._asdict()) for r in rows])
        if len(results) >= limit:
            break
    return results[:limit]
