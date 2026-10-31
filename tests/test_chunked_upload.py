import io
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

def test_chunked_resumable_upload_flow(client):
    full_csv = b"id,item,cost\n1,Alpha,10.0\n2,Beta,20.0\n3,Gamma,30.0\n"
    chunk_size = 15
    chunks = [full_csv[i:i + chunk_size] for i in range(0, len(full_csv), chunk_size)]
    total_chunks = len(chunks)

    session_id = "test_chunk_session"

    # 1. Init upload
    init_res = client.post(
        "/api/datasets/upload/init",
        json={
            "session_id": session_id,
            "filename": "chunked_items.csv",
            "file_size_bytes": len(full_csv),
            "total_chunks": total_chunks,
            "chunk_size_bytes": chunk_size,
        },
    )
    assert init_res.status_code == 200
    upload_id = init_res.json()["upload_id"]

    # 2. Upload chunk 0 and chunk 2 (simulate network interruption skipping chunk 1)
    client.post(
        "/api/datasets/upload/chunk",
        data={"upload_id": upload_id, "chunk_index": 0},
        files={"chunk_file": ("chunk_0.part", chunks[0], "application/octet-stream")},
    )
    if total_chunks > 2:
        client.post(
            "/api/datasets/upload/chunk",
            data={"upload_id": upload_id, "chunk_index": 2},
            files={"chunk_file": ("chunk_2.part", chunks[2], "application/octet-stream")},
        )

    # 3. Check status to resume
    status_res = client.get(f"/api/datasets/upload/status?upload_id={upload_id}")
    assert status_res.status_code == 200
    st_data = status_res.json()
    assert 0 in st_data["uploaded_chunks"]
    assert st_data["is_complete"] is False

    # 4. Resume by uploading missing chunk 1 and any remaining
    for idx in range(total_chunks):
        if idx not in st_data["uploaded_chunks"]:
            client.post(
                "/api/datasets/upload/chunk",
                data={"upload_id": upload_id, "chunk_index": idx},
                files={"chunk_file": (f"chunk_{idx}.part", chunks[idx], "application/octet-stream")},
            )

    # 5. Verify status is complete
    final_status = client.get(f"/api/datasets/upload/status?upload_id={upload_id}").json()
    assert final_status["is_complete"] is True
    assert len(final_status["uploaded_chunks"]) == total_chunks

    # 6. Complete and trigger validation pipeline
    complete_res = client.post(
        "/api/datasets/upload/complete",
        json={"upload_id": upload_id, "session_id": session_id},
    )
    assert complete_res.status_code == 200
    val_data = complete_res.json()
    assert val_data["can_register"] is True
    assert val_data["row_count"] == 3
    assert val_data["column_count"] == 3
