import re
from typing import List, Dict, Any, Tuple, Optional
import duckdb

class GroundingEvaluationResult:
    def __init__(
        self,
        precision_score: float,
        supported_claims: List[str],
        unsupported_claims: List[str],
        table_recall_score: float,
        feasibility_status: str,
        notes: List[str],
    ):
        self.precision_score = precision_score
        self.supported_claims = supported_claims
        self.unsupported_claims = unsupported_claims
        self.table_recall_score = table_recall_score
        self.feasibility_status = feasibility_status
        self.notes = notes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "grounding_precision": round(self.precision_score, 2),
            "table_recall": round(self.table_recall_score, 2),
            "feasibility_status": self.feasibility_status,
            "supported_claims": self.supported_claims,
            "unsupported_claims": self.unsupported_claims,
            "notes": self.notes,
        }

class GroundingValidator:
    # Regex to capture numeric values, currency ($XX.XX), millions/billions shorthand, percentages
    NUMBER_PATTERN = re.compile(
        r"(?:\$\s*)?(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s*(?:M|k|K|B|%|million|billion)?\b"
    )

    @classmethod
    def evaluate(
        cls,
        user_message: str,
        narrative: str,
        sql_query: str,
        query_records: List[Dict[str, Any]],
        conn: duckdb.DuckDBPyConnection,
    ) -> GroundingEvaluationResult:
        notes = []

        # 1. Evaluate Numerical Claim Grounding (Precision@k)
        precision, supported, unsupported = cls._evaluate_claims_precision(
            narrative, query_records
        )
        if unsupported:
            notes.append(
                f"Found {len(unsupported)} claim(s) in narrative not strictly matching retrieved database values."
            )

        # 2. Evaluate Schema Retrieval Recall (Recall@k)
        recall = cls._evaluate_table_recall(user_message, sql_query, conn)

        # 3. Feasibility Pre-Check
        feasibility = cls._check_feasibility(user_message, conn)
        if feasibility != "FEASIBLE":
            notes.append(f"Query feasibility advisory: {feasibility}")

        return GroundingEvaluationResult(
            precision_score=precision,
            supported_claims=supported,
            unsupported_claims=unsupported,
            table_recall_score=recall,
            feasibility_status=feasibility,
            notes=notes,
        )

    @classmethod
    def _evaluate_claims_precision(
        cls, narrative: str, query_records: List[Dict[str, Any]]
    ) -> Tuple[float, List[str], List[str]]:
        if not query_records:
            return 1.0, [], []

        # Collect all numeric values present in DuckDB records
        ground_truth_numbers = set()
        for r in query_records:
            for v in r.values():
                if isinstance(v, (int, float)):
                    ground_truth_numbers.add(round(float(v), 2))
                    # Also add integer representation
                    ground_truth_numbers.add(int(v))

        # Extract numerical tokens from narrative
        matches = cls.NUMBER_PATTERN.finditer(narrative)
        claims = []
        for m in matches:
            raw = m.group(0).strip()
            # Ignore standard calendar years like 2023, 2024
            if raw in ("2023", "2024", "2025", "2026", "1", "2"):
                continue
            claims.append(raw)

        if not claims:
            return 1.0, [], []

        supported = []
        unsupported = []

        for claim in claims:
            is_supported = cls._is_claim_supported(claim, ground_truth_numbers)
            if is_supported:
                supported.append(claim)
            else:
                unsupported.append(claim)

        precision = len(supported) / len(claims) if claims else 1.0
        return precision, supported, unsupported

    @classmethod
    def _is_claim_supported(cls, claim: str, ground_truth_numbers: set) -> bool:
        # Normalize claim text to float
        clean = re.sub(r"[^\d.]", "", claim)
        if not clean:
            return True
        try:
            val = float(clean)
        except ValueError:
            return True

        # Check direct or multiplier match
        multipliers = [1.0]
        if "M" in claim or "million" in claim.lower():
            multipliers.extend([1_000_000.0])
        elif "k" in claim or "K" in claim:
            multipliers.extend([1_000.0])

        for mult in multipliers:
            candidate = round(val * mult, 2)
            for gt in ground_truth_numbers:
                # 2% relative tolerance or $0.05 absolute tolerance for rounding
                diff = abs(candidate - gt)
                if diff <= 0.1 or (gt > 0 and diff / gt < 0.03):
                    return True

        return False

    @classmethod
    def _evaluate_table_recall(
        cls, user_message: str, sql_query: str, conn: duckdb.DuckDBPyConnection
    ) -> float:
        # Determine candidate tables mentioned or needed
        all_tables = [t[0].lower() for t in conn.execute("SHOW TABLES").fetchall()]
        if not all_tables:
            return 1.0

        tables_in_sql = [t for t in all_tables if re.search(rf"\b{t}\b", sql_query.lower())]

        # Count tables referenced in question
        relevant_tables = []
        msg_lower = user_message.lower()
        keyword_table_map = {
            "order": "orders",
            "item": "order_items",
            "product": "products",
            "pay": "payment",
            "ship": "shipments",
            "carrier": "shipments",
            "customer": "customers",
            "review": "reviews",
            "supplier": "suppliers",
            "revenue": "orders",
            "sales": "orders",
            "category": "products",
        }

        for kw, tbl in keyword_table_map.items():
            if kw in msg_lower and tbl in all_tables and tbl not in relevant_tables:
                relevant_tables.append(tbl)

        if not relevant_tables:
            return 1.0 if tables_in_sql else 0.0

        recalled = sum(1 for t in relevant_tables if t in tables_in_sql)
        return recalled / len(relevant_tables)

    @classmethod
    def _check_feasibility(cls, user_message: str, conn: duckdb.DuckDBPyConnection) -> str:
        # Pre-screen if user asks for unanswerable concepts like weather, salaries, stocks
        unsupported_keywords = [
            "salary", "employee", "weather", "temperature", "stock price", "inventory", "margin"
        ]
        msg = user_message.lower()
        for kw in unsupported_keywords:
            if kw in msg:
                return f"POSSIBLY_UNANSWERABLE: Question refers to '{kw}' which is not in dataset schema."
        return "FEASIBLE"
