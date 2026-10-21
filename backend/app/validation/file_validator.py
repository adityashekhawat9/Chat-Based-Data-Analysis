import csv
import io
import re
import sys
from typing import List, Tuple, Optional
from backend.app.models.dataset import ValidationIssue, Severity, IssueCode

# Configure CSV field size limit to handle large text columns without throwing 500 error
try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2147483647)

# Maximum file size: 1GB (supports large multi-chunk datasets)
MAX_FILE_SIZE = 1024 * 1024 * 1024

# Dangerous patterns for formula/script injection
SCRIPT_TAG_REGEX = re.compile(r"<\s*script[^>]*>|javascript:|vbscript:|<\s*iframe[^>]*>", re.IGNORECASE)
FORMULA_INJECTION_REGEX = re.compile(r"^[\=\+\-\@\t\r](?:\s*cmd|\s*powershell|\s*calc|.*DDE|.*EXEC)", re.IGNORECASE)
FORMULA_GLOBAL_REGEX = re.compile(r"(?:^|[\r\n,;\t])\s*[\=\+\-\@\t\r](?:\s*cmd|\s*powershell|\s*calc|.*DDE|.*EXEC)", re.IGNORECASE)

class FileValidationResult:
    def __init__(
        self,
        is_valid: bool,
        decoded_text: str = "",
        encoding: str = "utf-8",
        raw_rows: Optional[List[List[str]]] = None,
        issues: Optional[List[ValidationIssue]] = None
    ):
        self.is_valid = is_valid
        self.decoded_text = decoded_text
        self.encoding = encoding
        self.raw_rows = raw_rows or []
        self.issues = issues or []

class FileValidator:
    def __init__(self, max_file_size: int = MAX_FILE_SIZE):
        self.max_file_size = max_file_size

    def validate_file(self, filename: str, content_bytes: bytes) -> FileValidationResult:
        issues: List[ValidationIssue] = []

        # 1. Check file size
        file_size = len(content_bytes)
        if file_size == 0:
            issues.append(
                ValidationIssue(
                    code=IssueCode.EMPTY_FILE.value,
                    severity=Severity.BLOCKING,
                    message="The uploaded file is empty (0 bytes).",
                    recommended_action="Ensure the file has valid data before uploading."
                )
            )
            return FileValidationResult(is_valid=False, issues=issues)

        if file_size > self.max_file_size:
            issues.append(
                ValidationIssue(
                    code=IssueCode.FILE_TOO_LARGE.value,
                    severity=Severity.BLOCKING,
                    message=f"File size ({file_size / (1024 * 1024):.2f} MB) exceeds maximum allowed limit ({self.max_file_size / (1024 * 1024):.0f} MB).",
                    recommended_action="Compress the file or upload a smaller sample."
                )
            )
            return FileValidationResult(is_valid=False, issues=issues)

        # 2. Check format extension
        lower_name = filename.lower()
        if not lower_name.endswith((".csv", ".txt")):
            issues.append(
                ValidationIssue(
                    code=IssueCode.UNSUPPORTED_FORMAT.value,
                    severity=Severity.BLOCKING,
                    message=f"Unsupported file format for '{filename}'. Only .csv files are supported for tabular analysis.",
                    recommended_action="Convert or export your dataset as a standard comma-separated (.csv) file."
                )
            )
            return FileValidationResult(is_valid=False, issues=issues)

        # 3. Decode bytes with encoding detection
        decoded_text, encoding = self._decode_bytes(content_bytes)
        if decoded_text is None:
            issues.append(
                ValidationIssue(
                    code=IssueCode.INVALID_ENCODING.value,
                    severity=Severity.BLOCKING,
                    message="Unable to decode file with standard encodings (UTF-8, Latin-1, Windows-1252).",
                    recommended_action="Save and export the CSV with UTF-8 encoding."
                )
            )
            return FileValidationResult(is_valid=False, issues=issues)

        # 4. Parse CSV stream
        try:
            # Detect delimiter using Sniffer if possible, fallback to comma
            sample = decoded_text[:4096]
            try:
                sniffer = csv.Sniffer()
                dialect = sniffer.sniff(sample, delimiters=",;\t|")
                delimiter = dialect.delimiter
            except Exception:
                delimiter = ","

            reader = csv.reader(io.StringIO(decoded_text), delimiter=delimiter)
            raw_rows = list(reader)
        except Exception as e:
            issues.append(
                ValidationIssue(
                    code=IssueCode.MALFORMED_CSV.value,
                    severity=Severity.BLOCKING,
                    message=f"Failed to parse CSV stream: {str(e)}",
                    recommended_action="Inspect the CSV file for unescaped quotes or corrupted delimiters."
                )
            )
            return FileValidationResult(is_valid=False, issues=issues)

        if not raw_rows or len(raw_rows) == 0:
            issues.append(
                ValidationIssue(
                    code=IssueCode.EMPTY_FILE.value,
                    severity=Severity.BLOCKING,
                    message="CSV file does not contain any readable rows.",
                    recommended_action="Ensure the CSV contains a header and data rows."
                )
            )
            return FileValidationResult(is_valid=False, issues=issues)

        # 5. Check for script injection or dangerous formula execution across full file
        injection_issues = self._check_script_injection(raw_rows, decoded_text)
        issues.extend(injection_issues)

        has_blocking = any(issue.severity == Severity.BLOCKING for issue in issues)
        return FileValidationResult(
            is_valid=not has_blocking,
            decoded_text=decoded_text,
            encoding=encoding,
            raw_rows=raw_rows,
            issues=issues
        )

    def _decode_bytes(self, content_bytes: bytes) -> Tuple[Optional[str], str]:
        encodings = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]
        for enc in encodings:
            try:
                decoded = content_bytes.decode(enc)
                return decoded, enc
            except (UnicodeDecodeError, LookupError):
                continue
        return None, ""

    def _check_script_injection(
        self, raw_rows: List[List[str]], decoded_text: str = ""
    ) -> List[ValidationIssue]:
        issues = []

        # Fast global check across entire decoded text to guarantee zero row-limit blind spots
        if decoded_text:
            if SCRIPT_TAG_REGEX.search(decoded_text):
                issues.append(
                    ValidationIssue(
                        code=IssueCode.SCRIPT_INJECTION_RISK.value,
                        severity=Severity.BLOCKING,
                        message="Potentially dangerous script or iframe tag detected in dataset content.",
                        affected_count=1,
                        recommended_action="Remove embedded HTML/JavaScript tags from data fields."
                    )
                )
                return issues

            if FORMULA_GLOBAL_REGEX.search(decoded_text):
                issues.append(
                    ValidationIssue(
                        code=IssueCode.SCRIPT_INJECTION_RISK.value,
                        severity=Severity.BLOCKING,
                        message="Executable spreadsheet formula command detected in dataset content.",
                        affected_count=1,
                        recommended_action="Sanitize spreadsheet formula prefixes before uploading."
                    )
                )
                return issues

        # Granular row-by-row inspection with wide window
        total_rows = len(raw_rows)
        # Inspect all rows up to 10,000; if larger, inspect head and tail chunks
        if total_rows <= 10000:
            inspect_indices = range(total_rows)
        else:
            inspect_indices = list(range(5000)) + list(range(total_rows - 5000, total_rows))

        for row_idx in inspect_indices:
            row = raw_rows[row_idx]
            for col_idx, cell in enumerate(row):
                val = cell.strip()
                if not val:
                    continue
                # Check HTML/JS script injection
                if SCRIPT_TAG_REGEX.search(val):
                    issues.append(
                        ValidationIssue(
                            code=IssueCode.SCRIPT_INJECTION_RISK.value,
                            severity=Severity.BLOCKING,
                            message=f"Potentially dangerous script tag detected at row {row_idx + 1}, column {col_idx + 1}.",
                            affected_count=1,
                            recommended_action="Remove embedded HTML/JavaScript tags from data fields."
                        )
                    )
                    return issues

                # Check executable formula injection
                if FORMULA_INJECTION_REGEX.search(val):
                    issues.append(
                        ValidationIssue(
                            code=IssueCode.SCRIPT_INJECTION_RISK.value,
                            severity=Severity.BLOCKING,
                            message=f"Executable spreadsheet formula command detected at row {row_idx + 1}, column {col_idx + 1}: '{val[:30]}'",
                            affected_count=1,
                            recommended_action="Sanitize spreadsheet formula prefixes before uploading."
                        )
                    )
                    return issues
        return issues

