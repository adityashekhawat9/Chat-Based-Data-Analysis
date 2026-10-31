import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.api.datasets import registry

def test_multi_tenant_isolation(client):
    csv_alpha = b"id,val\n1,AlphaData\n"
    csv_beta = b"id,val\n2,BetaData\n"

    # Tenant Alpha Upload & Register
    r_a = client.post(
        "/api/datasets/validate",
        headers={"X-Tenant-ID": "tenant_alpha"},
        data={"session_id": "sess_a"},
        files={"file": ("alpha.csv", csv_alpha, "text/csv")},
    )
    assert r_a.status_code == 200
    h_a = r_a.json()["content_hash"]

    reg_a = client.post(
        "/api/datasets/register",
        headers={"X-Tenant-ID": "tenant_alpha"},
        json={"session_id": "sess_a", "content_hash": h_a, "table_name": "alpha_table"},
    )
    assert reg_a.status_code == 201

    # Tenant Beta Upload & Register
    r_b = client.post(
        "/api/datasets/validate",
        headers={"X-Tenant-ID": "tenant_beta"},
        data={"session_id": "sess_b"},
        files={"file": ("beta.csv", csv_beta, "text/csv")},
    )
    assert r_b.status_code == 200
    h_b = r_b.json()["content_hash"]

    reg_b = client.post(
        "/api/datasets/register",
        headers={"X-Tenant-ID": "tenant_beta"},
        json={"session_id": "sess_b", "content_hash": h_b, "table_name": "beta_table"},
    )
    assert reg_b.status_code == 201

    # Verify Tenant Alpha sees ONLY alpha_table
    conn_a = registry.get_tenant_duckdb("tenant_alpha")
    tables_a = [t[0] for t in conn_a.execute("SHOW TABLES").fetchall()]
    assert "alpha_table" in tables_a
    assert "beta_table" not in tables_a

    # Verify Tenant Beta sees ONLY beta_table
    conn_b = registry.get_tenant_duckdb("tenant_beta")
    tables_b = [t[0] for t in conn_b.execute("SHOW TABLES").fetchall()]
    assert "beta_table" in tables_b
    assert "alpha_table" not in tables_b

    # Verify cross-tenant querying in DuckDB fails
    with pytest.raises(Exception):
        conn_a.execute("SELECT * FROM beta_table").fetchall()

def test_tenant_id_traversal_rejection(client):
    # Attempt directory traversal with ../../
    res = client.post(
        "/api/datasets/validate",
        headers={"X-Tenant-ID": "../../etc"},
        data={"session_id": "sess_hack"},
        files={"file": ("test.csv", b"a,b\n1,2\n", "text/csv")},
    )
    assert res.status_code == 400
    assert "Invalid tenant_id" in res.json()["detail"]
