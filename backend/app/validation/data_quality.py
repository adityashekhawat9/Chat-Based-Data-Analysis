import re
from typing import List, Dict, Any, Optional
from collections import Counter
from backend.app.models.dataset import (
    ColumnProfile,
    ValidationIssue,
    Severity,
    IssueCode,
)

class DataQualityConfig:
    def __init__(
        self,
        missing_rate_warning_threshold: float = 20.0,
        duplicate_rows_threshold: int = 1,
        type_inconsistency_threshold: float = 10.0,
    ):
        self.missing_rate_warning_threshold = missing_rate_warning_threshold
        self.duplicate_rows_threshold = duplicate_rows_threshold
        self.type_inconsistency_threshold = type_inconsistency_threshold

class DataQualityChecker:
    def __init__(self, config: Optional[DataQualityConfig] = None):
        self.config = config or DataQualityConfig()

    def check_quality(
        self,
        raw_headers: List[str],
        data_rows: List[List[str]],
        column_profiles: List[ColumnProfile],
    ) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        total_rows = len(data_rows)

        if total_rows == 0:
            return issues

        # 1. Detect duplicate rows (exact full row matches)
        seen_rows = set()
        duplicate_row_count = 0
        for r in data_rows:
            tup = tuple(r)
            if tup in seen_rows:
                duplicate_row_count += 1
            else:
                seen_rows.add(tup)

        if duplicate_row_count >= self.config.duplicate_rows_threshold:
            pct = round((duplicate_row_count / total_rows) * 100, 2)
            issues.append(
                ValidationIssue(
                    code=IssueCode.DUPLICATE_ROWS.value,
                    severity=Severity.WARNING,
                    message=f"Dataset contains {duplicate_row_count} duplicate rows ({pct}% of total records).",
                    affected_count=duplicate_row_count,
                    recommended_action="Review if duplicate records represent legitimate repeat events or duplicate entries.",
                )
            )

        # 2. Check each column profile for quality issues
        for profile in column_profiles:
            # 2a. Fully empty column
            if profile.null_count == total_rows or profile.null_percentage >= 100.0:
                issues.append(
                    ValidationIssue(
                        code=IssueCode.FULLY_EMPTY_COLUMN.value,
                        severity=Severity.WARNING,
                        column=profile.raw_name,
                        affected_count=total_rows,
                        message=f"Column '{profile.raw_name}' is completely empty (100% null/blank values).",
                        recommended_action="Consider excluding this column from analytical queries to save resources.",
                    )
                )
            # 2b. High missing value rate
            elif profile.null_percentage >= self.config.missing_rate_warning_threshold:
                issues.append(
                    ValidationIssue(
                        code=IssueCode.HIGH_MISSING_RATE.value,
                        severity=Severity.WARNING,
                        column=profile.raw_name,
                        affected_count=profile.null_count,
                        message=f"Column '{profile.raw_name}' has a high missing rate of {profile.null_percentage}%.",
                        recommended_action="Queries filtering on this column may drop significant numbers of rows.",
                    )
                )

            # 2c. Likely generated index column
            if self._is_likely_index_column(profile, data_rows, total_rows):
                issues.append(
                    ValidationIssue(
                        code=IssueCode.LIKELY_INDEX_COLUMN.value,
                        severity=Severity.WARNING,
                        column=profile.raw_name,
                        affected_count=total_rows,
                        message=f"Column '{profile.raw_name}' appears to be an exported dataframe index.",
                        recommended_action="Verify if this column is an artificial row index or a true domain identifier.",
                    )
                )

        # 3. Detect invalid type conversions / mixed types
        type_issues = self._check_type_consistency(raw_headers, data_rows, column_profiles)
        issues.extend(type_issues)

        return issues

    def _is_likely_index_column(
        self, profile: ColumnProfile, data_rows: List[List[str]], total_rows: int
    ) -> bool:
        lower_name = profile.raw_name.strip().lower()
        if lower_name in ("unnamed: 0", "index", "_index"):
            return True

        if profile.inferred_type == "INT" and profile.is_unique and total_rows > 5:
            col_idx = [p.name for p in [profile]][0]  # sample check first 5 rows
            # check if first 5 rows are 0, 1, 2, 3, 4 or 1, 2, 3, 4, 5
            try:
                sample_ints = [int(p) for p in profile.sample_values[:3] if p.isdigit()]
                if sample_ints == [0, 1, 2] or sample_ints == [1, 2, 3]:
                    if lower_name in ("id", "order_id", "customer_id", "product_id"):
                        return False  # True domain ID
                    if "unnamed" in lower_name:
                        return True
            except Exception:
                pass
        return False

    def _check_type_consistency(
        self,
        raw_headers: List[str],
        data_rows: List[List[str]],
        column_profiles: List[ColumnProfile],
    ) -> List[ValidationIssue]:
        issues = []
        sample_rows = data_rows[:1000]
        if not sample_rows:
            return issues

        for idx, profile in enumerate(column_profiles):
            if profile.inferred_type not in ("INT", "FLOAT", "DATETIME"):
                continue

            # Check if there are rogue strings that failed to convert
            non_conformant = 0
            for row in sample_rows:
                if idx >= len(row):
                    continue
                val = row[idx].strip()
                if not val or val.lower() in ("null", "none", "nan", "n/a", ""):
                    continue

                if profile.inferred_type in ("INT", "FLOAT"):
                    try:
                        float(val)
                    except ValueError:
                        non_conformant += 1

            if non_conformant > 0:
                pct = round((non_conformant / len(sample_rows)) * 100, 2)
                if pct > 0:
                    issues.append(
                        ValidationIssue(
                            code=IssueCode.MIXED_TYPES.value,
                            severity=Severity.WARNING,
                            column=profile.raw_name,
                            affected_count=non_conformant,
                            message=f"Column '{profile.raw_name}' has mixed data types: {non_conformant} values ({pct}%) do not conform to {profile.inferred_type}.",
                            recommended_action=f"Cleanse inconsistent entries in '{profile.raw_name}' before performing numerical operations.",
                        )
                    )
        return issues
