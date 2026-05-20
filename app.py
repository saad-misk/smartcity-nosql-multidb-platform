"""
SmartCity Platform — Flask Application Entry Point
Run locally: python app.py
Run via Docker: docker-compose up
"""

import os
from flask import Flask, render_template, send_from_directory
from routes.citizens  import citizens_bp
from routes.requests  import requests_bp
from routes.analytics import analytics_bp
from routes.graph     import graph_bp

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("SECRET_KEY", "smartcity-dev-secret")

# Register blueprints
app.register_blueprint(citizens_bp)
app.register_blueprint(requests_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(graph_bp)


# ─── Frontend Pages ─────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/submit")
def submit():
    return render_template("submit.html")


@app.route("/graph")
def graph_page():
    return render_template("graph.html")


# ─── Health Check ────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    from db import redis_client as redis_c
    status = {
        "app":    "ok",
        "redis":  "ok" if redis_c.ping() else "unavailable",
    }
    try:
        from db import mongo_client as mongo
        mongo.get_db().command("ping")
        status["mongodb"] = "ok"
    except Exception:
        status["mongodb"] = "unavailable"

    try:
        from db import neo4j_client as neo4j
        driver = neo4j.get_driver()
        driver.verify_connectivity()
        driver.close()
        status["neo4j"] = "ok"
    except Exception:
        status["neo4j"] = "unavailable"

    try:
        from db import elasticsearch_client as es
        status["elasticsearch"] = "ok" if es.get_client().ping() else "unavailable"
    except Exception:
        status["elasticsearch"] = "unavailable"

    return {"status": status}, 200


if __name__ == "__main__":
    print("\n🏙️  SmartCity Platform starting...")
    print("   http://localhost:5000\n")
    app.run(host="0.0.0.0", port=5000, debug=True)
