import pytest
from backend.app.validation.schema_profiler import SchemaProfiler
from backend.app.validation.data_quality import DataQualityChecker, DataQualityConfig
from backend.app.models.dataset import Severity, IssueCode

def test_clean_data_no_warnings():
    profiler = SchemaProfiler()
    checker = DataQualityChecker()
    rows = [
        ["id", "name", "price"],
        ["1", "Apple", "1.50"],
        ["2", "Banana", "0.75"],
        ["3", "Cherry", "2.00"],
    ]
    res = profiler.profile_schema(rows)
    issues = checker.check_quality(res.raw_headers, rows[1:], res.column_profiles)
    assert len(issues) == 0

def test_fully_empty_column():
    profiler = SchemaProfiler()
    checker = DataQualityChecker()
    rows = [
        ["id", "name", "notes"],
        ["1", "Apple", ""],
        ["2", "Banana", "  "],
        ["3", "Cherry", "null"],
    ]
    res = profiler.profile_schema(rows)
    issues = checker.check_quality(res.raw_headers, rows[1:], res.column_profiles)
    codes = [i.code for i in issues]
    assert IssueCode.FULLY_EMPTY_COLUMN.value in codes
    assert any(i.severity == Severity.WARNING for i in issues)

def test_likely_index_column():
    profiler = SchemaProfiler()
    checker = DataQualityChecker()
    rows = [
        ["Unnamed: 0", "product", "sales"],
        ["0", "Laptop", "100"],
        ["1", "Mouse", "50"],
        ["2", "Keyboard", "80"],
        ["3", "Monitor", "60"],
        ["4", "Headphones", "40"],
        ["5", "Desk", "20"],
    ]
    res = profiler.profile_schema(rows)
    issues = checker.check_quality(res.raw_headers, rows[1:], res.column_profiles)
    codes = [i.code for i in issues]
    assert IssueCode.LIKELY_INDEX_COLUMN.value in codes

def test_duplicate_rows():
    profiler = SchemaProfiler()
    checker = DataQualityChecker()
    rows = [
        ["id", "item"],
        ["1", "Pen"],
        ["2", "Notebook"],
        ["1", "Pen"],  # Duplicate row
    ]
    res = profiler.profile_schema(rows)
    issues = checker.check_quality(res.raw_headers, rows[1:], res.column_profiles)
    codes = [i.code for i in issues]
    assert IssueCode.DUPLICATE_ROWS.value in codes
    assert any(i.severity == Severity.WARNING for i in issues)

def test_high_missing_rate():
    profiler = SchemaProfiler()
    checker = DataQualityChecker(DataQualityConfig(missing_rate_warning_threshold=20.0))
    rows = [
        ["id", "category"],
        ["1", "Tech"],
        ["2", ""],
        ["3", ""],
        ["4", "Home"],
    ]  # 50% missing in category
    res = profiler.profile_schema(rows)
    issues = checker.check_quality(res.raw_headers, rows[1:], res.column_profiles)
    codes = [i.code for i in issues]
    assert IssueCode.HIGH_MISSING_RATE.value in codes

def test_mixed_types():
    profiler = SchemaProfiler()
    checker = DataQualityChecker()
    rows = [
        ["id", "score"],
        ["1", "95.5"],
        ["2", "88.0"],
        ["3", "NOT_AVAILABLE"],  # String in numeric column
        ["4", "76.2"],
        ["5", "91.0"],
    ]
    res = profiler.profile_schema(rows)
    issues = checker.check_quality(res.raw_headers, rows[1:], res.column_profiles)
    codes = [i.code for i in issues]
    assert IssueCode.MIXED_TYPES.value in codes
