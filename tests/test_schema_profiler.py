import pytest
from backend.app.validation.schema_profiler import SchemaProfiler
from backend.app.models.dataset import Severity, IssueCode

def test_valid_schema():
    profiler = SchemaProfiler()
    rows = [
        ["user_id", "user_name", "signup_date", "is_active", "balance"],
        ["1", "Alice", "2024-01-01", "true", "150.50"],
        ["2", "Bob", "2024-01-02", "false", "200.00"],
    ]
    res = profiler.profile_schema(rows)
    assert res.is_valid is True
    assert len(res.column_profiles) == 5
    types = {p.name: p.inferred_type for p in res.column_profiles}
    assert types["user_id"] == "INT"
    assert types["user_name"] == "STRING"
    assert types["signup_date"] == "DATETIME"
    assert types["is_active"] == "BOOLEAN"
    assert types["balance"] == "FLOAT"

def test_empty_column_header():
    profiler = SchemaProfiler()
    rows = [
        ["id", "", "price"],
        ["1", "Item", "10.0"],
    ]
    res = profiler.profile_schema(rows)
    assert res.is_valid is False
    codes = [i.code for i in res.issues]
    assert IssueCode.EMPTY_COLUMN_HEADER.value in codes
    assert any(i.severity == Severity.BLOCKING for i in res.issues)

def test_duplicate_column_headers():
    profiler = SchemaProfiler()
    rows = [
        ["product_id", "name", "Product_Id"],
        ["101", "Widget", "101"],
    ]
    res = profiler.profile_schema(rows)
    assert res.is_valid is False
    codes = [i.code for i in res.issues]
    assert IssueCode.DUPLICATE_COLUMNS.value in codes
    assert any(i.severity == Severity.BLOCKING for i in res.issues)

def test_identifier_normalization():
    profiler = SchemaProfiler()
    rows = [
        ["Order ID #", "Customer Email Address!", "Total Price ($)"],
        ["1", "a@b.com", "99.99"],
    ]
    res = profiler.profile_schema(rows)
    assert res.is_valid is True
    assert res.normalized_headers == ["order_id", "customer_email_address", "total_price"]
