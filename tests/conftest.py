import os
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.api.datasets import registry, chunked_uploader

@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    test_dir = str(tmp_path / "test_data")
    monkeypatch.setattr(registry, "base_storage_dir", test_dir)
    monkeypatch.setattr(chunked_uploader, "base_storage", test_dir)
    registry._duckdb_conns = {}
    registry._registered = {}
    registry._staged = {}
    registry._hash_to_dataset = {}
    yield
    for conn in list(registry._duckdb_conns.values()):
        try:
            conn.close()
        except Exception:
            pass
    registry._duckdb_conns = {}

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def sample_csv_dir():
    # Robust resolution to find data/Online Shop 2024
    curr = os.path.dirname(os.path.abspath(__file__))
    while curr and curr != "/":
        candidate = os.path.join(curr, "data", "Online Shop 2024")
        if os.path.exists(candidate):
            return candidate
        curr = os.path.dirname(curr)
    return "/Users/aadi/Desktop/Online Shop 2024"

