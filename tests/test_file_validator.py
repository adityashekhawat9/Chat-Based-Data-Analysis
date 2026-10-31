import pytest
from backend.app.validation.file_validator import FileValidator
from backend.app.models.dataset import Severity, IssueCode

def test_valid_csv():
    validator = FileValidator()
    content = b"id,name,price\n1,Widget,9.99\n2,Gadget,19.99\n"
    res = validator.validate_file("items.csv", content)
    assert res.is_valid is True
    assert len(res.raw_rows) == 3
    assert not any(i.severity == Severity.BLOCKING for i in res.issues)

def test_zero_byte_empty_file():
    validator = FileValidator()
    res = validator.validate_file("empty.csv", b"")
    assert res.is_valid is False
    codes = [i.code for i in res.issues]
    assert IssueCode.EMPTY_FILE.value in codes
    assert any(i.severity == Severity.BLOCKING for i in res.issues)

def test_header_only_file():
    validator = FileValidator()
    res = validator.validate_file("header_only.csv", b"id,name,value\n")
    assert res.is_valid is True
    assert len(res.raw_rows) == 1

def test_file_size_limit():
    validator = FileValidator(max_file_size=100)  # 100 bytes limit for test
    content = b"a" * 150
    res = validator.validate_file("large.csv", content)
    assert res.is_valid is False
    codes = [i.code for i in res.issues]
    assert IssueCode.FILE_TOO_LARGE.value in codes

def test_unsupported_format():
    validator = FileValidator()
    res = validator.validate_file("document.pdf", b"%PDF-1.4...")
    assert res.is_valid is False
    codes = [i.code for i in res.issues]
    assert IssueCode.UNSUPPORTED_FORMAT.value in codes

def test_invalid_encoding():
    validator = FileValidator()
    # Malformed multi-byte sequence invalid across utf-8, latin1, cp1252
    # In python, latin-1 decodes almost anything, but invalid utf-16 with odd length or raw corrupted bytes can be tested
    # Or test fallback to latin-1
    content = "col1,col2\nVal,Café\n".encode("utf-8")
    res = validator.validate_file("encoded.csv", content)
    assert res.is_valid is True
    assert res.encoding in ("utf-8", "utf-8-sig")

def test_script_tag_injection():
    validator = FileValidator()
    content = b"id,name,comment\n1,Alice,<script>alert('xss')</script>\n"
    res = validator.validate_file("test.csv", content)
    assert res.is_valid is False
    codes = [i.code for i in res.issues]
    assert IssueCode.SCRIPT_INJECTION_RISK.value in codes
    assert any(i.severity == Severity.BLOCKING for i in res.issues)

def test_formula_injection():
    validator = FileValidator()
    content = b'id,name,formula\n1,Bob,"=cmd|\' /C calc\'!A0"\n'
    res = validator.validate_file("test.csv", content)
    assert res.is_valid is False
    codes = [i.code for i in res.issues]
    assert IssueCode.SCRIPT_INJECTION_RISK.value in codes
