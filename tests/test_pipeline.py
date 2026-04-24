import json
import time
import uuid
from datetime import datetime, timezone

import requests

PRODUCER_URL = "http://localhost:8000"
CLICKHOUSE_HTTP_URL = "http://localhost:8123"


def _query_clickhouse(query: str):
    resp = requests.get(
        CLICKHOUSE_HTTP_URL,
        params={"database": "online_cinema", "query": query.strip()},
        timeout=10,
    )
    resp.raise_for_status()
    lines = [line for line in resp.text.splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def test_event_ingestion_pipeline():
    event_id = str(uuid.uuid4())
    user_id = f"test_user_{uuid.uuid4()}"
    movie_id = f"test_movie_{uuid.uuid4()}"

    event_payload = {
        "event_id": event_id,
        "user_id": user_id,
        "movie_id": movie_id,
        "event_type": "VIEW_STARTED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "device_type": "MOBILE",
        "session_id": str(uuid.uuid4()),
        "progress_seconds": 0,
    }

    response = requests.post(f"{PRODUCER_URL}/events", json=event_payload, timeout=10)
    assert response.status_code == 200, f"Producer failed: {response.text}"

    max_retries = 20
    found = False
    for _ in range(max_retries):
        time.sleep(1.5)
        rows = _query_clickhouse(
            f"""
            SELECT event_id, user_id, event_type
            FROM movie_events
            WHERE event_id = '{event_id}'
            FORMAT JSONEachRow
        """
        )
        if rows:
            found = True
            row = rows[0]
            assert row["event_id"] == event_id
            assert row["user_id"] == user_id
            assert row["event_type"] == "VIEW_STARTED"
            break

    assert found, f"Event {event_id} not found in ClickHouse after {max_retries} retries"
