import re
from typing import Tuple, Optional

from backend.app.query.nlp_guardrails import NLPGuardrails, MAX_USER_MESSAGE_LENGTH

# Prohibited mutating statements & system operations
DISALLOWED_KEYWORDS = [
    r"\bDROP\b",
    r"\bDELETE\b",
    r"\bUPDATE\b",
    r"\bINSERT\b",
    r"\bALTER\b",
    r"\bCREATE\b",
    r"\bTRUNCATE\b",
    r"\bEXEC\b",
    r"\bEXECUTE\b",
    r"\bATTACH\b",
    r"\bCOPY\b",
    r"\bEXPORT\b",
    r"\bIMPORT\b",
    r"\bPRAGMA\b",
    r"\bCALL\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    r"\bSET\b",
    r"\bRESET\b",
    r"\bLOAD\b",
    r"\bINSTALL\b",
    r"\bCHECKPOINT\b",
]
DISALLOWED_REGEX = re.compile("|".join(DISALLOWED_KEYWORDS), re.IGNORECASE)

# Prohibited internal system metadata and diagnostic functions
DISALLOWED_SYSTEM_FUNCTIONS = [
    r"\bduckdb_[a-zA-Z0-9_]+\b",
    r"\bpragma_[a-zA-Z0-9_]+\b",
    r"\bcurrent_setting\b",
    r"\b(?:current_user|session_user)\s*\(\s*\)",
]
DISALLOWED_SYSTEM_REGEX = re.compile("|".join(DISALLOWED_SYSTEM_FUNCTIONS), re.IGNORECASE)

# Dangerous filesystem and external-access table functions
EXTERNAL_ACCESS_KEYWORDS = [
    r"\bread_(?:csv|csv_auto|parquet|json|json_auto|text|blob)\b",
    r"\bscan_(?:parquet|csv)\b",
    r"\b(?:glob|httpfs|delta_scan|iceberg_scan|sqlite_scan|postgres_scan|mysql_scan)\b",
]
EXTERNAL_ACCESS_REGEX = re.compile("|".join(EXTERNAL_ACCESS_KEYWORDS), re.IGNORECASE)

# Direct host filesystem path patterns in queries
FILESYSTEM_PATH_REGEX = re.compile(
    r"""(?:\bFROM|\bJOIN)\s+['"](?:/|[a-zA-Z]:|\.\.?/)[^'"]+['"]""",
    re.IGNORECASE,
)

MUTATION_REFUSAL_MESSAGE = (
    "I apologize, but this system operates in a strict read-only analytical mode to protect your data integrity and security. "
    "I do not have authorization or permissions to edit, modify, delete, or drop data from your tables (such as DELETE, UPDATE, DROP, ALTER, or TRUNCATE operations).\n\n"
    "Within our analytical capabilities, I would be glad to help you explore, filter, aggregate, or visualize your datasets without modifying the source records (for example, displaying a filtered view that excludes specific records or calculating metrics). "
    "Please let me know how you would like to analyze the data!"
)

FILESYSTEM_ACCESS_REFUSAL = (
    "I apologize, but direct access to host files, filesystem paths, or external table functions is prohibited. "
    "You may only query registered tables in your dataset catalog."
)

SYSTEM_METADATA_ACCESS_REFUSAL = (
    "I apologize, but access to internal database system settings, secrets, and diagnostic functions is prohibited."
)

# User-intent patterns for data mutation / modification
MUTATION_INTENT_PATTERNS = [
    r"\b(delete|remove|erase|purge)\b.*\b(from|table|row|record|customer|order|item|entry|entries|data)\b",
    r"\b(drop|truncate|alter|modify|edit|insert|update)\b.*\b(table|database|schema|row|column|record|data|into|set)\b",
    r"\b(delete|drop|truncate|alter|edit|modify|remove)\b\s+([a-zA-Z0-9_]+|\d+)",
    r"\b(can you|please|i want to|could you|help me)\s+(?:to\s+)?(delete|drop|truncate|alter|edit|update|modify|remove|purge|erase)\b",
    r"^\s*(delete|drop|truncate|alter|update|remove|edit|modify)\b",
    r"\bdelete\s+from\b",
    r"\binsert\s+into\b",
    r"\bupdate\s+\w+\s+set\b",
]
MUTATION_INTENT_REGEX = re.compile("|".join(MUTATION_INTENT_PATTERNS), re.IGNORECASE)

MAX_RESULT_LIMIT = 1000

class SQLGuardrailError(Exception):
    pass

class SQLGuardrails:
    @staticmethod
    def is_mutation_intent(message: str) -> bool:
        """
        Detects if user natural language message is attempting data mutation or deletion,
        using spaCy semantic NLP analysis with regex safety fallback.
        """
        if not message:
            return False
        return NLPGuardrails.analyze_mutation_intent(message)

    @staticmethod
    def clean_sql(raw_sql: str) -> str:
        # Strip markdown fences
        sql = re.sub(r"^```(?:sql)?\s*", "", raw_sql.strip(), flags=re.IGNORECASE)
        sql = re.sub(r"\s*```$", "", sql.strip())
        sql = sql.strip().rstrip(";")
        return sql

    @staticmethod
    def strip_literals_and_comments(sql: str) -> str:
        """
        Strips comments and string literals to prevent false-positives
        when keywords, paths, or semicolons appear inside data values.
        """
        # Strip multi-line comments /* ... */
        s = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
        # Strip single-line comments -- ...
        s = re.sub(r"--[^\n]*", " ", s)
        # Strip single-quoted string literals with support for doubled quotes and backslash
        s = re.sub(r"'(?:''|\\.|[^'])*'", "''", s)
        return s

    @classmethod
    def validate_and_sanitize(cls, raw_sql: str) -> str:
        cleaned = cls.clean_sql(raw_sql)
        if not cleaned:
            raise SQLGuardrailError("Generated SQL query is empty.")

        # 1. Strip string literals and comments to inspect SQL structure
        stripped = cls.strip_literals_and_comments(cleaned)

        # 2. Check for multiple statements (only unquoted semicolons)
        statements = [s.strip() for s in stripped.split(";") if s.strip()]
        if len(statements) > 1:
            raise SQLGuardrailError("Multiple SQL statements in a single query are prohibited.")

        # 3. Check for external file system access & table functions (Vector 1)
        if EXTERNAL_ACCESS_REGEX.search(stripped) or FILESYSTEM_PATH_REGEX.search(cleaned):
            raise SQLGuardrailError(FILESYSTEM_ACCESS_REFUSAL)

        # 4. Check for internal DuckDB system & metadata functions (Vector 4)
        if DISALLOWED_SYSTEM_REGEX.search(stripped):
            raise SQLGuardrailError(SYSTEM_METADATA_ACCESS_REFUSAL)

        # 4. Check for prohibited mutating keywords outside string literals (Vector 2)
        match = DISALLOWED_REGEX.search(stripped)
        if match:
            raise SQLGuardrailError(MUTATION_REFUSAL_MESSAGE)

        # 5. Must start with SELECT or WITH
        normalized = stripped.lstrip().upper()
        if not (normalized.startswith("SELECT") or normalized.startswith("WITH")):
            raise SQLGuardrailError(MUTATION_REFUSAL_MESSAGE)

        # 6. Memory exhaustion & hard LIMIT clamping (Vector 3)
        limit_match = re.search(r"\bLIMIT\s+(\d+)\b", cleaned, re.IGNORECASE)
        if limit_match:
            user_limit = int(limit_match.group(1))
            if user_limit > MAX_RESULT_LIMIT:
                # Clamp excessive limit down to safety ceiling
                cleaned = (
                    cleaned[: limit_match.start()]
                    + f"LIMIT {MAX_RESULT_LIMIT}"
                    + cleaned[limit_match.end() :]
                )
        else:
            # Query has no explicit LIMIT: check if it's a pure scalar aggregation
            is_pure_scalar = bool(
                re.match(r"^SELECT\s+(?:COUNT|SUM|AVG|MIN|MAX)\s*\([^)]*\)\s+FROM\b", normalized)
                and "GROUP BY" not in normalized
            )
            if not is_pure_scalar:
                cleaned = f"{cleaned} LIMIT {MAX_RESULT_LIMIT}"

        return cleaned
