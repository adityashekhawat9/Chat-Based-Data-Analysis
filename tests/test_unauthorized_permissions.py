import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.query.sql_guardrails import SQLGuardrails, MUTATION_REFUSAL_MESSAGE

client = TestClient(app)

TENANT_HEADER = {"X-Tenant-ID": "test_unauth_guardrails_tenant"}

def test_mutation_intent_regex_coverage():
    """Verify regex accurately identifies mutating prompts without false positives."""
    positive_cases = [
        "delete customer 177 and 8965",
        "can you delete customer 177?",
        "DROP table customers",
        "drop database test",
        "truncate orders",
        "can you edit customer 8965 name to Jane",
        "update orders set status = 'Completed'",
        "alter table customers add column phone",
        "remove customer 177 from the table",
        "please erase all records",
        "purge data from table",
        "insert into customers values (1, 'Test')",
    ]
    for prompt in positive_cases:
        assert SQLGuardrails.is_mutation_intent(prompt) is True, f"Failed to detect mutation: {prompt}"

    negative_cases = [
        "What was the total revenue in 2024?",
        "Show top 5 customers by spend",
        "Which product had the highest sales?",
        "Monthly orders breakdown",
        "Find customer 177 and 8965 details",
        "List all customers",
    ]
    for prompt in negative_cases:
        assert SQLGuardrails.is_mutation_intent(prompt) is False, f"False positive detected: {prompt}"

def test_api_chat_returns_polite_refusal_for_mutations():
    """Ensure POST /api/chat returns polite refusal message and blank SQL for mutating requests."""
    mutations = [
        "delete customer 177",
        "drop table orders",
        "edit order 102",
        "truncate table payment",
    ]
    for m in mutations:
        resp = client.post(
            "/api/chat",
            json={"session_id": "test_sess_unauth", "message": m},
            headers=TENANT_HEADER,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "I apologize" in data["answer"]
        assert "read-only" in data["answer"]
        assert data["sql_query"] == ""
        assert data["chart"] is None
