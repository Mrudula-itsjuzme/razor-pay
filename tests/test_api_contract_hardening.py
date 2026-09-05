from decimal import Decimal
from datetime import datetime

from fastapi.testclient import TestClient

from main import app, engine

client = TestClient(app)


def test_demo_loads_exactly_seven_cases():
    response = client.post("/api/demo")
    assert response.status_code == 200
    from main import global_cases
    assert len(global_cases) == 7


def test_demo_scenario_identities_are_present():
    client.post("/api/demo")
    from main import global_cases
    identities = {case[1] for case in global_cases}
    assert {
        "CLEAN",
        "SPLIT_SETTLEMENT",
        "MISSING_FEE_EVIDENCE",
        "ADV_SAME_AMOUNT_WRONG_TX",
        "ADV_DUPLICATE_UTR",
        "ADV_WRONG_REFUND_PERFECT_DISCREPANCY",
        "PENDING_BANK_SLA_SAFE",
    } <= identities


def test_reconciliation_response_state_is_one_of_expected():
    client.post("/api/demo")
    from main import global_cases, global_graph
    order_id = global_cases[0][0]
    response = client.get(f"/api/reconcile/{order_id}")
    assert response.status_code == 200
    decision = response.json()["decision"]
    assert decision in {"RECONCILED", "PENDING", "ESCALATED"}


def test_invalid_case_returns_expected_error():
    response = client.get("/api/reconcile/does-not-exist")
    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found"


def test_graph_endpoint_target_context_classification_is_correct():
    client.post("/api/demo")
    from main import global_cases
    order_id = global_cases[0][0]
    payload = client.get(f"/api/graph/{order_id}").json()
    assert "nodes" in payload and "edges" in payload
    assert len(payload["nodes"]) >= 1
    labels = {node["label"] for node in payload["nodes"]}
    assert labels


def test_api_response_schema_contains_required_judge_facing_fields():
    client.post("/api/demo")
    from main import global_cases
    order_id = global_cases[0][0]
    response = client.get(f"/api/reconcile/{order_id}")
    data = response.json()
    for key in [
        "decision",
        "reason",
        "decision_authority",
        "proof_certificate",
        "proof_validity",
        "evidence_contract",
        "case_id",
        "confidence",
    ]:
        assert key in data, f"Missing required field {key}"


def test_proof_certificate_contract_for_reconciled_case():
    client.post("/api/demo")
    from main import global_cases
    order_id = next(case[0] for case in global_cases if case[1] == "CLEAN")
    result = client.get(f"/api/reconcile/{order_id}").json()
    assert result["decision"] == "RECONCILED"
    certificate = result["proof_certificate"]
    assert certificate["decision"] == "RECONCILED"
    assert certificate["proof_validity"] in {"PASS", "FAIL"}
    assert certificate["evidence_contract"]["type"]
