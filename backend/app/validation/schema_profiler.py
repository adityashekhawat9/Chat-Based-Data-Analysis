import re
from datetime import datetime
from collections import Counter
from typing import List, Tuple, Dict, Any, Optional
from backend.app.models.dataset import (
    ColumnProfile,
    ValidationIssue,
    Severity,
    IssueCode,
)

DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S",
    "%d-%m-%Y",
    "%m/%d/%Y",
    "%Y/%m/%d",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
]

class SchemaProfileResult:
    def __init__(
        self,
        is_valid: bool,
        raw_headers: List[str],
        normalized_headers: List[str],
        column_profiles: List[ColumnProfile],
        issues: List[ValidationIssue],
    ):
        self.is_valid = is_valid
        self.raw_headers = raw_headers
        self.normalized_headers = normalized_headers
        self.column_profiles = column_profiles
        self.issues = issues

class SchemaProfiler:
    def profile_schema(self, raw_rows: List[List[str]]) -> SchemaProfileResult:
        issues: List[ValidationIssue] = []

        if not raw_rows:
            issues.append(
                ValidationIssue(
                    code=IssueCode.EMPTY_FILE.value,
                    severity=Severity.BLOCKING,
                    message="Dataset has no rows to profile.",
                    recommended_action="Ensure the CSV contains a valid header row.",
                )
            )
            return SchemaProfileResult(
                is_valid=False,
                raw_headers=[],
                normalized_headers=[],
                column_profiles=[],
                issues=issues,
            )

        raw_headers = raw_rows[0]
        data_rows = raw_rows[1:]

        # 1. Inspect raw headers for empty column names
        empty_indices = []
        for idx, h in enumerate(raw_headers):
            if not h or not h.strip():
                empty_indices.append(idx + 1)

        if empty_indices:
            issues.append(
                ValidationIssue(
                    code=IssueCode.EMPTY_COLUMN_HEADER.value,
                    severity=Severity.BLOCKING,
                    message=f"Header contains empty/blank column names at position(s): {empty_indices}.",
                    affected_count=len(empty_indices),
                    recommended_action="Provide descriptive names for all column headers in the CSV.",
                )
            )

        # 2. Inspect raw headers for duplicate column names
        header_counts = Counter(h.strip().lower() for h in raw_headers if h and h.strip())
        duplicates = [name for name, count in header_counts.items() if count > 1]
        if duplicates:
            issues.append(
                ValidationIssue(
                    code=IssueCode.DUPLICATE_COLUMNS.value,
                    severity=Severity.BLOCKING,
                    message=f"Duplicate column header names detected: {duplicates}.",
                    affected_count=len(duplicates),
                    recommended_action="Rename duplicate headers to ensure each column has a distinct name.",
                )
            )

        has_blocking = any(issue.severity == Severity.BLOCKING for issue in issues)
        if has_blocking:
            return SchemaProfileResult(
                is_valid=False,
                raw_headers=raw_headers,
                normalized_headers=[],
                column_profiles=[],
                issues=issues,
            )

        # 3. Generate safe normalized identifiers (snake_case)
        normalized_headers = self._normalize_headers(raw_headers)

        # 4. Profile column types and nullability
        column_profiles = self._profile_columns(raw_headers, normalized_headers, data_rows)

        return SchemaProfileResult(
            is_valid=True,
            raw_headers=raw_headers,
            normalized_headers=normalized_headers,
            column_profiles=column_profiles,
            issues=issues,
        )

    def _normalize_headers(self, headers: List[str]) -> List[str]:
        normalized = []
        seen = set()
        for idx, h in enumerate(headers):
            # Clean string to lowercase alphanumeric + underscores
            clean = re.sub(r"[^\w\s]", "", h.strip()).strip().lower()
            clean = re.sub(r"[\s\-]+", "_", clean)
            if not clean:
                clean = f"column_{idx+1}"
            # Ensure unique in case of edge cases
            candidate = clean
            suffix = 1
            while candidate in seen:
                candidate = f"{clean}_{suffix}"
                suffix += 1
            seen.add(candidate)
            normalized.append(candidate)
        return normalized

    def _infer_cell_type(self, val: str) -> str:
        if not val or val.lower() in ("null", "none", "nan", "n/a", "na", ""):
            return "NULL"
        val = val.strip()
        if re.match(r"^-?\d+$", val):
            return "INT"
        if re.match(r"^-?\d+\.\d+$", val):
            return "FLOAT"
        if val.lower() in ("true", "false"):
            return "BOOLEAN"
        for fmt in DATE_FORMATS:
            try:
                datetime.strptime(val, fmt)
                return "DATETIME"
            except ValueError:
                pass
        return "STRING"

    def _profile_columns(
        self,
        raw_headers: List[str],
        normalized_headers: List[str],
        data_rows: List[List[str]],
    ) -> List[ColumnProfile]:
        profiles = []
        total_rows = len(data_rows)
        sample_limit = min(total_rows, 2000)

        for col_idx, raw_name in enumerate(raw_headers):
            norm_name = normalized_headers[col_idx]
            values = [
                row[col_idx].strip() if col_idx < len(row) else ""
                for row in data_rows
            ]

            null_count = sum(
                1 for v in values if not v or v.lower() in ("null", "none", "nan", "n/a", "")
            )
            null_pct = round((null_count / total_rows * 100), 2) if total_rows > 0 else 0.0

            non_null_sample = [
                v for v in values[:sample_limit]
                if v and v.lower() not in ("null", "none", "nan", "n/a", "")
            ]

            if not non_null_sample:
                inferred_type = "STRING"
            else:
                type_counts = Counter(self._infer_cell_type(v) for v in non_null_sample)
                inferred_type = type_counts.most_common(1)[0][0]

            distinct_vals = set(values)
            unique_count = len(distinct_vals)
            is_unique = (unique_count == total_rows and null_count == 0)
            sample_vals = [v for v in non_null_sample[:3]]

            profiles.append(
                ColumnProfile(
                    name=norm_name,
                    raw_name=raw_name,
                    inferred_type=inferred_type,
                    null_count=null_count,
                    null_percentage=null_pct,
                    unique_count=unique_count,
                    is_unique=is_unique,
                    sample_values=sample_vals,
                )
            )

        return profiles
