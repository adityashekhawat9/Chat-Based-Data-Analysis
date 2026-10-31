import os
import pytest
from backend.app.query.sql_guardrails import SQLGuardrails, SQLGuardrailError, FILESYSTEM_ACCESS_REFUSAL, MAX_RESULT_LIMIT
from backend.app.validation.file_validator import FileValidator
from backend.app.validation.dataset_registry import DatasetRegistry
import duckdb

# ==============================================================================
# Break Vector 1: Filesystem Exfiltration & External Table Function Protection
# ==============================================================================

def test_break_vector_1_read_csv_table_function_blocked():
    """Verify that attempting to read host files via read_csv is strictly blocked."""
    malicious_query = "SELECT * FROM read_csv('/etc/passwd')"
    with pytest.raises(SQLGuardrailError) as exc_info:
        SQLGuardrails.validate_and_sanitize(malicious_query)
    assert FILESYSTEM_ACCESS_REFUSAL in str(exc_info.value)

def test_break_vector_1_read_text_and_glob_blocked():
    """Verify read_text, glob, and other external table functions are rejected."""
    queries = [
        "SELECT * FROM read_text('/Users/aadi/.env')",
        "SELECT * FROM glob('/*')",
        "SELECT * FROM read_json('/etc/shadow')",
        "SELECT * FROM read_parquet('/var/data/secret.parquet')",
        "SELECT * FROM '/etc/passwd'",
    ]
    for q in queries:
        with pytest.raises(SQLGuardrailError) as exc_info:
            SQLGuardrails.validate_and_sanitize(q)
        assert FILESYSTEM_ACCESS_REFUSAL in str(exc_info.value) or "Multiple SQL" in str(exc_info.value)


# ==============================================================================
# Break Vector 2: False-Positive Semicolons & Keywords Inside String Literals
# ==============================================================================

def test_break_vector_2_semicolon_inside_string_literal_allowed():
    """Verify that semicolons inside string literals do NOT trigger 'Multiple SQL statements'."""
    legit_query = "SELECT * FROM products WHERE description = 'item 1; item 2; priority: high'"
    sanitized = SQLGuardrails.validate_and_sanitize(legit_query)
    assert "item 1; item 2; priority: high" in sanitized
    assert "LIMIT" in sanitized

def test_break_vector_2_mutating_keyword_inside_string_literal_allowed():
    """Verify that words like 'delete', 'drop', 'update' inside data filters are NOT rejected."""
    legit_query = "SELECT * FROM logs WHERE message LIKE '%Warning: drop in network traffic; please update connection%'"
    sanitized = SQLGuardrails.validate_and_sanitize(legit_query)
    assert "Warning: drop in network traffic" in sanitized

def test_break_vector_2_actual_multiple_statements_still_blocked():
    """Verify that multiple distinct SQL statements outside literals are still strictly blocked."""
    attack = "SELECT * FROM products; DROP TABLE customers;"
    with pytest.raises(SQLGuardrailError) as exc_info:
        SQLGuardrails.validate_and_sanitize(attack)
    assert "Multiple SQL statements in a single query are prohibited" in str(exc_info.value)


# ==============================================================================
# Break Vector 3: Memory Exhaustion & Result Set Clamping
# ==============================================================================

def test_break_vector_3_massive_limit_clamped():
    """Verify that an excessive limit (e.g. LIMIT 500000) is clamped to MAX_RESULT_LIMIT."""
    query = "SELECT * FROM transactions LIMIT 500000"
    sanitized = SQLGuardrails.validate_and_sanitize(query)
    assert f"LIMIT {MAX_RESULT_LIMIT}" in sanitized
    assert "500000" not in sanitized

def test_break_vector_3_group_by_auto_limit():
    """Verify that GROUP BY queries without limit receive an enforced safety LIMIT."""
    query = "SELECT category, count(*) FROM products GROUP BY category"
    sanitized = SQLGuardrails.validate_and_sanitize(query)
    assert f"LIMIT {MAX_RESULT_LIMIT}" in sanitized

def test_break_vector_3_scalar_count_preserved():
    """Verify that pure single-row aggregation like SELECT count(*) FROM t is preserved."""
    query = "SELECT count(*) FROM products"
    sanitized = SQLGuardrails.validate_and_sanitize(query)
    assert "LIMIT" not in sanitized

def test_break_vector_3_fetchmany_bounds_memory():
    """Verify _execute_to_records never allocates beyond 1,001 rows even on large tables."""
    from backend.app.query.llm_service import LLMService
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE TABLE huge AS SELECT range as id FROM range(5000)")
    llm = LLMService()
    records = llm._execute_to_records(conn, "SELECT * FROM huge")
    assert len(records) == 1001  # Clamped to 1001 max rows in Python memory


# ==============================================================================
# Break Vector 4: Script & Formula Injection on Row 501+ & Large Text Fields
# ==============================================================================

def test_break_vector_4_script_injection_on_row_501_blocked():
    """Verify that script injection on row 501 (past the old 500 row limit) is detected."""
    validator = FileValidator()
    # Generate 500 clean rows
    rows = ["id,content\n"]
    for i in range(1, 501):
        rows.append(f"{i},clean content item {i}\n")
    # Row 501 contains dangerous script tag
    rows.append("501,<script>alert('pwned')</script>\n")
    csv_bytes = "".join(rows).encode("utf-8")

    result = validator.validate_file("large_dataset.csv", csv_bytes)
    assert result.is_valid is False
    assert any(i.code == "SCRIPT_INJECTION_RISK" for i in result.issues)

def test_break_vector_4_formula_injection_on_row_600_blocked():
    """Verify executable formula injection on row 600+ is detected."""
    validator = FileValidator()
    rows = ["id,formula\n"]
    for i in range(1, 601):
        rows.append(f"{i},regular val {i}\n")
    rows.append("601,=cmd|' /C powershell -enc test'!A0\n")
    csv_bytes = "".join(rows).encode("utf-8")

    result = validator.validate_file("formula_test.csv", csv_bytes)
    assert result.is_valid is False
    assert any(i.code == "SCRIPT_INJECTION_RISK" for i in result.issues)

def test_break_vector_4_large_csv_field_does_not_crash():
    """Verify that fields exceeding 128 KB do not crash with _csv.Error field limit."""
    validator = FileValidator()
    # 150 KB string field
    large_text = "A" * (150 * 1024)
    csv_content = f"id,description\n1,{large_text}\n2,normal text\n"
    csv_bytes = csv_content.encode("utf-8")

    result = validator.validate_file("large_field.csv", csv_bytes)
    assert result.is_valid is True
    assert len(result.raw_rows) == 3


# ==============================================================================
# Break Vector 5: Table Name Sanitization & Cross-Session Overwrite Prevention
# ==============================================================================

def test_break_vector_5_reserved_sql_keywords_sanitized(tmp_path):
    """Verify that table names using reserved SQL keywords (e.g. 'order', 'group', 'user') are safe."""
    registry = DatasetRegistry(base_storage_dir=str(tmp_path))
    t1 = registry._resolve_table_name("tenant_test", "sess_1", "order")
    assert t1 == "tbl_order"

    t2 = registry._resolve_table_name("tenant_test", "sess_1", "group")
    assert t2 == "tbl_group"

    t3 = registry._resolve_table_name("tenant_test", "sess_1", "123_invalid")
    assert t3.startswith("tbl_")

    t4 = registry._resolve_table_name("tenant_test", "sess_1", "???")
    assert t4 == "tbl_dataset"

def test_break_vector_5_cross_session_table_overwrite_prevented(tmp_path):
    """Verify that Session B cannot overwrite Session A's identically named table in the same tenant."""
    registry = DatasetRegistry(base_storage_dir=str(tmp_path))
    tenant_id = "tenant_corp"

    # Simulate Session A registering table 'customers'
    t_a = registry._resolve_table_name(tenant_id, "session_A", "customers")
    assert t_a == "customers"

    # Register in metadata for session_A
    from backend.app.validation.dataset_registry import RegisteredDataset
    import datetime
    mock_ds_a = RegisteredDataset(
        dataset_id="ds_a",
        tenant_id=tenant_id,
        session_id="session_A",
        table_name="customers",
        filename="customers.csv",
        content_hash="hash_a",
        row_count=100,
        column_count=3,
        columns=["id", "name", "email"],
        registered_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )
    registry._registered["ds_a"] = mock_ds_a

    # Now Session B uploads a file wanting table 'customers'
    t_b = registry._resolve_table_name(tenant_id, "session_B", "customers")
    # Must NOT be 'customers', must disambiguate to prevent destroying session A's table
    assert t_b == "customers_1"
    assert t_b != t_a
