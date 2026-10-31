import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.query.sql_guardrails import SQLGuardrails, SQLGuardrailError
from backend.app.api.datasets import registry

def test_sql_guardrails_read_only():
    # Valid SELECT
    assert "SELECT * FROM orders" in SQLGuardrails.validate_and_sanitize("SELECT * FROM orders")
    assert "WITH t AS (SELECT 1) SELECT * FROM t" in SQLGuardrails.validate_and_sanitize("WITH t AS (SELECT 1) SELECT * FROM t")

    # Prohibited mutating statements
    with pytest.raises(SQLGuardrailError):
        SQLGuardrails.validate_and_sanitize("DROP TABLE orders")

    with pytest.raises(SQLGuardrailError):
        SQLGuardrails.validate_and_sanitize("DELETE FROM orders WHERE id = 1")

    with pytest.raises(SQLGuardrailError):
        SQLGuardrails.validate_and_sanitize("UPDATE payment SET amount = 0")

    with pytest.raises(SQLGuardrailError):
        SQLGuardrails.validate_and_sanitize("INSERT INTO products VALUES (1, 'Hacked')")

    with pytest.raises(SQLGuardrailError):
        SQLGuardrails.validate_and_sanitize("ALTER TABLE customers ADD COLUMN hack TEXT")

    # Chained statements
    with pytest.raises(SQLGuardrailError):
        SQLGuardrails.validate_and_sanitize("SELECT * FROM orders; DROP TABLE customers")

def test_chat_without_datasets(client):
    res = client.post(
        "/api/chat",
        headers={"X-Tenant-ID": "empty_tenant_test"},
        json={"session_id": "empty_session_123", "message": "What is total revenue?"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "No datasets are currently registered" in data["answer"]
    assert data["sql_query"] == ""

def test_load_sample_dataset_and_chat_monthly_trend(client):
    session_id = "test_analytics_session"
    tenant_headers = {"X-Tenant-ID": "test_analytics_tenant"}
    # 1. Load sample dataset
    load_res = client.post(
        "/api/datasets/load-sample",
        headers=tenant_headers,
        json={"session_id": session_id},
    )
    assert load_res.status_code == 200
    datasets = load_res.json()["datasets"]
    assert len(datasets) == 8
    table_names = {d["table_name"] for d in datasets}
    assert "orders" in table_names
    assert "payment" in table_names
    assert "order_items" in table_names
    assert "products" in table_names

    # 2. Query monthly revenue trend
    chat_res = client.post(
        "/api/chat",
        headers=tenant_headers,
        json={
            "session_id": session_id,
            "message": "What is the monthly sales trend over the past year?",
        },
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["sql_query"] != ""
    assert "orders" in chat_data["sql_query"].lower()
    assert chat_data["chart"] is not None
    assert len(chat_data["chart"]["data"]) > 0
    assert len(chat_data["data_preview"]) > 0
    assert chat_data["execution_metrics"]["execution_time_ms"] > 0

def test_chat_cross_table_category_sales(client):
    session_id = "test_analytics_session"
    tenant_headers = {"X-Tenant-ID": "test_analytics_tenant"}
    client.post(
        "/api/datasets/load-sample",
        headers=tenant_headers,
        json={"session_id": session_id},
    )
    chat_res = client.post(
        "/api/chat",
        headers=tenant_headers,
        json={
            "session_id": session_id,
            "message": "Compare sales across product categories from two different CSVs",
        },
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert "category" in chat_data["sql_query"].lower()
    assert chat_data["chart"] is not None
    assert len(chat_data["chart"]["data"]) >= 4

def test_chat_geographic_distribution(client):
    session_id = "test_analytics_session"
    tenant_headers = {"X-Tenant-ID": "test_analytics_tenant"}
    client.post(
        "/api/datasets/load-sample",
        headers=tenant_headers,
        json={"session_id": session_id},
    )
    chat_res = client.post(
        "/api/chat",
        headers=tenant_headers,
        json={
            "session_id": session_id,
            "message": "Which states have the highest sales?",
        },
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert "state" in chat_data["sql_query"].lower()
    assert len(chat_data["data_preview"]) > 0
