import os
import duckdb
import pytest
from backend.app.validation.dataset_registry import DatasetRegistry
from backend.app.models.dataset import ValidationResponse

def test_duckdb_and_metadata_persistence_across_restart(tmp_path):
    storage_dir = str(tmp_path / "test_data")
    tenant_id = "test_persist_tenant"
    session_id = "test_persist_session"

    # 1. Initialize registry and register dataset
    reg1 = DatasetRegistry(base_storage_dir=storage_dir)
    csv_bytes = b"product_id,product_name,price\n1,Keyboard,49.99\n2,Mouse,24.50\n"
    content_hash = reg1.compute_content_hash(csv_bytes)

    val_resp = ValidationResponse(
        status="passed",
        session_id=session_id,
        filename="devices.csv",
        file_size_bytes=len(csv_bytes),
        content_hash=content_hash,
        is_duplicate=False,
        row_count=2,
        column_count=3,
        can_register=True,
    )
    reg1.stage_dataset(session_id, "devices.csv", csv_bytes, val_resp, tenant_id=tenant_id)
    reg_resp = reg1.register_staged_dataset(session_id, content_hash, "devices", tenant_id=tenant_id)
    assert reg_resp.table_name == "devices"

    # Close connections to simulate server shutdown
    for conn in reg1._duckdb_conns.values():
        conn.close()

    # 2. Simulate server restart: create brand-new registry instance
    reg2 = DatasetRegistry(base_storage_dir=storage_dir)

    # Verify metadata was restored from disk
    existing = reg2.get_existing_registration(session_id, content_hash, tenant_id=tenant_id)
    assert existing is not None
    assert existing.table_name == "devices"
    assert existing.row_count == 2

    # Verify physical DuckDB file persisted and can be queried directly
    conn2 = reg2.get_tenant_duckdb(tenant_id)
    count = conn2.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
    assert count == 2
    sum_price = conn2.execute("SELECT ROUND(SUM(price), 2) FROM devices").fetchone()[0]
    assert sum_price == 74.49
