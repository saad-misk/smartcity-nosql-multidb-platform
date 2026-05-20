"""
Elasticsearch Client — SmartCity
Purpose: similarity search on service-request descriptions so duplicate/related
         issues can be detected before a new request is stored.
"""

import os
from datetime import datetime, timezone
from elasticsearch import Elasticsearch

INDEX = "service_requests"


def get_client():
    url = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
    return Elasticsearch(url, request_timeout=2)


def ensure_index():
    client = get_client()
    if client.indices.exists(index=INDEX):
        return client

    client.indices.create(
        index=INDEX,
        settings={"index": {"number_of_shards": 1, "number_of_replicas": 0}},
        mappings={"properties": {
            "requestId":   {"type": "keyword"},
            "category":    {"type": "text",    "fields": {"keyword": {"type": "keyword"}}},
            "subCategory": {"type": "text",    "fields": {"keyword": {"type": "keyword"}}},
            "description": {"type": "text"},
            "areaName":    {"type": "text",    "fields": {"keyword": {"type": "keyword"}}},
            "status":      {"type": "keyword"},
            "priority":    {"type": "keyword"},
            "createdAt":   {"type": "date"},
        }},
    )
    return client


def index_request(request_id, doc):
    """Add or update a request document in the search index."""
    try:
        client = ensure_index()
        payload = {**doc, "requestId": request_id,
                   "indexedAt": datetime.now(timezone.utc)}
        client.index(index=INDEX, id=request_id, document=payload)
        return True
    except Exception:
        return False


def search_similar(description, category=None, area_name=None, limit=3):
    """
    Full-text search across description, category, and area.
    Returns (best_score, list_of_hits).
    Uses function_score to boost results that match the same category/area.
    """
    try:
        client = ensure_index()
        query_text = " ".join(filter(None, [description, category, area_name]))

        query = {
            "function_score": {
                "query": {
                    "multi_match": {
                        "query": query_text,
                        "fields": ["description^3", "category^2", "subCategory", "areaName"],
                        "fuzziness": "AUTO",
                    }
                },
                "functions": [
                    {"filter": {"term": {"category.keyword": category  or ""}}, "weight": 2.0},
                    {"filter": {"term": {"areaName.keyword":  area_name or ""}}, "weight": 1.5},
                ],
                "boost_mode": "sum",
                "score_mode": "sum",
            }
        }

        hits = get_client().search(
            index=INDEX, query=query, size=limit, track_total_hits=False
        ).get("hits", {}).get("hits", [])

        results    = [{"requestId": h["_id"], "score": h["_score"]} for h in hits]
        best_score = max((r["score"] for r in results), default=0.0)
        return best_score, results

    except Exception:
        return 0.0, []