import re
from typing import Tuple, Optional

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
    r"\bPRAGMA\b",
    r"\bCALL\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
]
DISALLOWED_REGEX = re.compile("|".join(DISALLOWED_KEYWORDS), re.IGNORECASE)

MUTATION_REFUSAL_MESSAGE = (
    "I apologize, but this system operates in a strict read-only analytical mode to protect your data integrity and security. "
    "I do not have authorization or permissions to edit, modify, delete, or drop data from your tables (such as DELETE, UPDATE, DROP, ALTER, or TRUNCATE operations).\n\n"
    "Within our analytical capabilities, I would be glad to help you explore, filter, aggregate, or visualize your datasets without modifying the source records (for example, displaying a filtered view that excludes specific records or calculating metrics). "
    "Please let me know how you would like to analyze the data!"
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

class SQLGuardrailError(Exception):
    pass

class SQLGuardrails:
    @staticmethod
    def is_mutation_intent(message: str) -> bool:
        """
        Detects if user natural language message is attempting data mutation or deletion.
        """
        if not message:
            return False
        return bool(MUTATION_INTENT_REGEX.search(message.strip()))

    @staticmethod
    def clean_sql(raw_sql: str) -> str:
        # Strip markdown fences
        sql = re.sub(r"^```(?:sql)?\s*", "", raw_sql.strip(), flags=re.IGNORECASE)
        sql = re.sub(r"\s*```$", "", sql.strip())
        sql = sql.strip().rstrip(";")
        return sql

    @classmethod
    def validate_and_sanitize(cls, raw_sql: str) -> str:
        cleaned = cls.clean_sql(raw_sql)
        if not cleaned:
            raise SQLGuardrailError("Generated SQL query is empty.")

        # Check for multiple statements (semicolon inside query)
        statements = [s.strip() for s in cleaned.split(";") if s.strip()]
        if len(statements) > 1:
            raise SQLGuardrailError("Multiple SQL statements in a single query are prohibited.")

        # Check for prohibited mutating keywords
        match = DISALLOWED_REGEX.search(cleaned)
        if match:
            raise SQLGuardrailError(MUTATION_REFUSAL_MESSAGE)

        # Must start with SELECT or WITH
        normalized = cleaned.lstrip()
        if not (normalized.upper().startswith("SELECT") or normalized.upper().startswith("WITH")):
            raise SQLGuardrailError(MUTATION_REFUSAL_MESSAGE)

        # Auto-append LIMIT 500 if no LIMIT and no GROUP BY
        if "LIMIT" not in normalized.upper() and "GROUP BY" not in normalized.upper() and "COUNT(" not in normalized.upper():
            cleaned = f"{cleaned} LIMIT 500"

        return cleaned
