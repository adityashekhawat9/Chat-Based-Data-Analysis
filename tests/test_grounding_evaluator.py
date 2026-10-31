import pytest
import duckdb
from backend.app.tracing.grounding_evaluator import GroundingValidator

def test_grounding_precision_fully_grounded():
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE TABLE sales AS SELECT 'Electronics' AS category, 150000.0 AS revenue")

    records = [{"category": "Electronics", "revenue": 150000.0}]
    narrative = "Electronics generated $150,000.00 in total revenue."

    res = GroundingValidator.evaluate(
        user_message="Sales for Electronics",
        narrative=narrative,
        sql_query="SELECT category, revenue FROM sales",
        query_records=records,
        conn=conn,
    )
    assert res.precision_score == 1.0
    assert len(res.unsupported_claims) == 0

def test_grounding_precision_hallucinated_claim():
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE TABLE sales AS SELECT 'Electronics' AS category, 150000.0 AS revenue")

    records = [{"category": "Electronics", "revenue": 150000.0}]
    # Hallucinates $999,999 which is not in query records
    narrative = "Electronics had $150,000.00 in revenue, but returns were $999,999.00."

    res = GroundingValidator.evaluate(
        user_message="Sales for Electronics",
        narrative=narrative,
        sql_query="SELECT category, revenue FROM sales",
        query_records=records,
        conn=conn,
    )
    assert res.precision_score < 1.0
    assert "999,999" in str(res.unsupported_claims)

def test_feasibility_check():
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE TABLE orders AS SELECT 1 AS order_id")

    res_good = GroundingValidator._check_feasibility("Show me order volume", conn)
    assert res_good == "FEASIBLE"

    res_unsupported = GroundingValidator._check_feasibility("What is the average employee salary?", conn)
    assert "POSSIBLY_UNANSWERABLE" in res_unsupported
