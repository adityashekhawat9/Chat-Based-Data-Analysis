import os
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.api.datasets import registry

@pytest.fixture(autouse=True)
def reset_registry():
    # Clear registry state before each test
    registry._staged.clear()
    registry._registered.clear()
    registry._hash_to_dataset.clear()
    registry._duckdb_conns.clear()

def test_validate_and_register_valid_csv(client, sample_csv_dir):
    products_csv_path = os.path.join(sample_csv_dir, "products.csv")
    with open(products_csv_path, "rb") as f:
        content = f.read()

    session_id = "test_sess_001"
    response = client.post(
        "/api/datasets/validate",
        data={"session_id": session_id},
        files={"file": ("products.csv", content, "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("passed", "warnings")
    assert data["can_register"] is True
    assert data["row_count"] == 2000
    assert data["column_count"] == 5
    assert data["is_duplicate"] is False
    content_hash = data["content_hash"]

    # Register the dataset
    reg_response = client.post(
        "/api/datasets/register",
        json={
            "session_id": session_id,
            "content_hash": content_hash,
            "table_name": "products",
        },
    )
    assert reg_response.status_code == 201
    reg_data = reg_response.json()
    assert reg_data["dataset_id"].startswith("ds_")
    assert reg_data["table_name"] == "products"
    assert reg_data["row_count"] == 2000

    # Verify table in DuckDB
    conn = registry.get_session_duckdb(session_id)
    result = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    assert result == 2000

def test_validate_zero_byte_file(client):
    response = client.post(
        "/api/datasets/validate",
        data={"session_id": "test_sess_002"},
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["status"] == "failed"
    assert data["can_register"] is False
    assert any(i["code"] == "EMPTY_FILE" for i in data["issues"])

def test_validate_script_injection(client):
    malicious_csv = b"id,user,bio\n1,evil,<script>alert('pwned')</script>\n"
    response = client.post(
        "/api/datasets/validate",
        data={"session_id": "test_sess_003"},
        files={"file": ("malicious.csv", malicious_csv, "text/csv")},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["status"] == "failed"
    assert data["can_register"] is False
    assert any(i["code"] == "SCRIPT_INJECTION_RISK" for i in data["issues"])

def test_identical_content_uploaded_under_different_filenames(client):
    csv_bytes = b"id,val\n1,Alpha\n2,Beta\n"
    session_id = "test_sess_idempotent"

    # Upload first under data1.csv and register
    r1 = client.post(
        "/api/datasets/validate",
        data={"session_id": session_id},
        files={"file": ("data1.csv", csv_bytes, "text/csv")},
    )
    assert r1.status_code == 200
    h1 = r1.json()["content_hash"]
    client.post(
        "/api/datasets/register",
        json={"session_id": session_id, "content_hash": h1, "table_name": "data1"},
    )

    # Upload same content under different filename data2.csv
    r2 = client.post(
        "/api/datasets/validate",
        data={"session_id": session_id},
        files={"file": ("data2.csv", csv_bytes, "text/csv")},
    )
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["is_duplicate"] is True
    assert d2["existing_dataset_id"] is not None
    assert d2["content_hash"] == h1

def test_different_content_uploaded_under_same_filename(client):
    content_a = b"id,val\n1,First\n"
    content_b = b"id,val\n2,Second\n"
    session_id = "test_sess_diff"

    r1 = client.post(
        "/api/datasets/validate",
        data={"session_id": session_id},
        files={"file": ("data.csv", content_a, "text/csv")},
    )
    assert r1.status_code == 200
    assert r1.json()["is_duplicate"] is False

    r2 = client.post(
        "/api/datasets/validate",
        data={"session_id": session_id},
        files={"file": ("data.csv", content_b, "text/csv")},
    )
    assert r2.status_code == 200
    assert r2.json()["is_duplicate"] is False
    assert r1.json()["content_hash"] != r2.json()["content_hash"]

def test_repeated_registration_within_session(client):
    csv_bytes = b"id,score\n1,100\n"
    session_id = "test_sess_repeat"

    r = client.post(
        "/api/datasets/validate",
        data={"session_id": session_id},
        files={"file": ("score.csv", csv_bytes, "text/csv")},
    )
    h = r.json()["content_hash"]

    reg1 = client.post(
        "/api/datasets/register",
        json={"session_id": session_id, "content_hash": h, "table_name": "score"},
    )
    assert reg1.status_code == 201
    id1 = reg1.json()["dataset_id"]

    # Register again with same hash
    reg2 = client.post(
        "/api/datasets/register",
        json={"session_id": session_id, "content_hash": h, "table_name": "score"},
    )
    assert reg2.status_code == 201
    assert reg2.json()["dataset_id"] == id1

def test_attempts_to_register_rejected_dataset(client):
    # Empty column header creates blocking error
    bad_csv = b"id,,price\n1,test,10\n"
    session_id = "test_sess_reject"

    r = client.post(
        "/api/datasets/validate",
        data={"session_id": session_id},
        files={"file": ("bad.csv", bad_csv, "text/csv")},
    )
    assert r.status_code == 422
    h = r.json()["content_hash"]

    # Attempt to force registration of rejected dataset
    reg = client.post(
        "/api/datasets/register",
        json={"session_id": session_id, "content_hash": h},
    )
    assert reg.status_code == 400
    assert "blocking validation errors" in reg.json()["detail"]

def test_toctou_prevention_unknown_hash(client):
    # Attempting to register an unvalidated/spoofed hash
    reg = client.post(
        "/api/datasets/register",
        json={"session_id": "fake_sess", "content_hash": "deadbeef" * 8},
    )
    assert reg.status_code == 400
    assert "No staged dataset found" in reg.json()["detail"]

def test_session_datasets_listing(client):
    session_id = "test_sess_list"
    csv1 = b"id,x\n1,10\n"
    csv2 = b"id,y\n1,20\n"

    r1 = client.post(
        "/api/datasets/validate",
        data={"session_id": session_id},
        files={"file": ("tbl1.csv", csv1, "text/csv")},
    )
    client.post(
        "/api/datasets/register",
        json={"session_id": session_id, "content_hash": r1.json()["content_hash"]},
    )

    r2 = client.post(
        "/api/datasets/validate",
        data={"session_id": session_id},
        files={"file": ("tbl2.csv", csv2, "text/csv")},
    )
    client.post(
        "/api/datasets/register",
        json={"session_id": session_id, "content_hash": r2.json()["content_hash"]},
    )

    list_resp = client.get(f"/api/datasets/sessions/{session_id}")
    assert list_resp.status_code == 200
    datasets = list_resp.json()["datasets"]
    assert len(datasets) == 2
    assert {d["filename"] for d in datasets} == {"tbl1.csv", "tbl2.csv"}


def test_register_batch_datasets(client):
    session_id = "test_sess_batch_reg"
    csv1 = b"id,dept,salary\n1,HR,50000\n2,ENG,90000\n"
    csv2 = b"id,project,hours\n1,Apollo,120\n2,Gemini,85\n"

    r1 = client.post(
        "/api/datasets/validate",
        data={"session_id": session_id},
        files={"file": ("departments.csv", csv1, "text/csv")},
    )
    assert r1.status_code == 200
    h1 = r1.json()["content_hash"]

    r2 = client.post(
        "/api/datasets/validate",
        data={"session_id": session_id},
        files={"file": ("projects.csv", csv2, "text/csv")},
    )
    assert r2.status_code == 200
    h2 = r2.json()["content_hash"]

    batch_resp = client.post(
        "/api/datasets/register-batch",
        json={
            "items": [
                {"session_id": session_id, "content_hash": h1, "table_name": "departments"},
                {"session_id": session_id, "content_hash": h2, "table_name": "projects"},
            ]
        },
    )
    assert batch_resp.status_code == 200
    batch_data = batch_resp.json()
    assert len(batch_data["registered"]) == 2
    assert len(batch_data["errors"]) == 0
    registered_tables = [d["table_name"] for d in batch_data["registered"]]
    assert "departments" in registered_tables
    assert "projects" in registered_tables

