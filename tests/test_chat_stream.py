import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

def test_chat_stream_sse_flow(client):
    session_id = "test_stream_session"

    # Preload sample dataset
    load_res = client.post(
        "/api/datasets/load-sample",
        headers={"X-Tenant-ID": "test_stream_tenant"},
        json={"session_id": session_id},
    )
    assert load_res.status_code == 200

    # Call SSE stream endpoint
    with client.stream(
        "POST",
        "/api/chat/stream",
        headers={"X-Tenant-ID": "test_stream_tenant"},
        json={"session_id": session_id, "message": "What is the monthly sales trend?"},
    ) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        events = []
        for line in response.iter_lines():
            if line.startswith("event: "):
                events.append(line.replace("event: ", "").strip())

        # Verify key SSE event sequence
        assert "pipeline_step" in events
        assert "sql" in events
        assert "execution" in events
        assert "token" in events
        assert "grounding" in events
        assert "done" in events
