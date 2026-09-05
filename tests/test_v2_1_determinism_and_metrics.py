import json
from datetime import datetime
from decimal import Decimal

import pytest

from evaluation.datagen_v2_1 import generate_complex_dataset_v2_1
from evaluation.metrics import evaluate_system
from graph import ProvenanceGraph


def _normalize_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _canonical_record_signature(records):
    signatures = []
    for rec in sorted(records, key=lambda r: (type(r).__name__, getattr(r, "order_id", getattr(r, "payment_id", getattr(r, "settlement_id", getattr(r, "bank_transaction_id", getattr(r, "ledger_entry_id", ""))))))):
        payload = {}
        for key, value in sorted(rec.__dict__.items()):
            if key.startswith("_"):
                continue
            payload[key] = _normalize_value(value)
        signatures.append((type(rec).__name__, tuple(sorted(payload.items()))))
    return tuple(signatures)


def _case_fingerprint(records, case_id, ground_truth):
    relevant = []
    for rec in records:
        if getattr(rec, "order_id", None) == case_id:
            relevant.append(rec)
        elif getattr(rec, "payment_id", None) and any(getattr(rec, "payment_id", None) == p.payment_id for p in records if type(p).__name__ == "Payment" and p.order_id == case_id):
            relevant.append(rec)
        elif getattr(rec, "settlement_id", None) and any(getattr(rec, "settlement_id", None) == s.settlement_id for s in records if type(s).__name__ == "Settlement" and any(item.payment_id in [p.payment_id for p in records if type(p).__name__ == "Payment" and p.order_id == case_id] for item in records if type(item).__name__ == "SettlementItem" and item.settlement_id == s.settlement_id)):
            relevant.append(rec)
    return (case_id, ground_truth, _canonical_record_signature(relevant))


def _dataset_signature(records, cases):
    return tuple(_case_fingerprint(records, case_id, ground_truth) for case_id, ground_truth in cases)


def _strip_volatile_fields(obj):
    if isinstance(obj, dict):
        cleaned = {}
        for key, value in obj.items():
            if key == "timestamp":
                continue
            cleaned[key] = _strip_volatile_fields(value)
        return cleaned
    if isinstance(obj, list):
        return [_strip_volatile_fields(item) for item in obj]
    return obj


def make_graph(records):
    g = ProvenanceGraph()
    for rec in records:
        t = type(rec).__name__
        if t == "Order":
            g.add_order(rec)
        elif t == "Payment":
            g.add_payment(rec)
        elif t == "Refund":
            g.add_refund(rec)
        elif t == "Fee":
            g.add_fee(rec)
        elif t == "Tax":
            g.add_tax(rec)
        elif t == "BankTransaction":
            g.add_bank_transaction(rec)

    for rec in records:
        if type(rec).__name__ == "Settlement":
            items = [r for r in records if type(r).__name__ == "SettlementItem" and r.settlement_id == rec.settlement_id]
            g.add_settlement(rec, items)

    for n, data in g.g.nodes(data=True):
        if data.get("type") == "BankTransaction":
            tx = data["data"]
            if tx.reference:
                for sn, sdata in g.g.nodes(data=True):
                    if sdata.get("type") == "Settlement" and sdata["data"].reference == tx.reference:
                        g.link_bank_transaction_to_settlement(tx.bank_transaction_id, sdata["data"].settlement_id)
    return g


def test_v2_1_dataset_is_deterministic_with_fixed_seed():
    records_a, cases_a, as_of_a = generate_complex_dataset_v2_1(seed=4242)
    records_b, cases_b, as_of_b = generate_complex_dataset_v2_1(seed=4242)

    assert as_of_a == as_of_b
    assert cases_a == cases_b
    assert len(records_a) == len(records_b)
    assert _dataset_signature(records_a, cases_a) == _dataset_signature(records_b, cases_b)


def test_v2_1_seed_changes_generated_case_values():
    records_a, cases_a, _ = generate_complex_dataset_v2_1(seed=4242)
    records_b, cases_b, _ = generate_complex_dataset_v2_1(seed=4243)

    assert cases_a != cases_b or _dataset_signature(records_a, cases_a) != _dataset_signature(records_b, cases_b)


def test_v2_1_evaluation_results_are_deterministic_and_bounded():
    records_a, cases_a, as_of_a = generate_complex_dataset_v2_1(seed=4242)
    graph_a = make_graph(records_a)
    metrics_a = evaluate_system(4, cases_a, graph_a, as_of_time=as_of_a)

    records_b, cases_b, as_of_b = generate_complex_dataset_v2_1(seed=4242)
    graph_b = make_graph(records_b)
    metrics_b = evaluate_system(4, cases_b, graph_b, as_of_time=as_of_b)

    for key in ["tp", "fp", "tn", "fn", "precision", "recall", "f1", "exc_precision", "exc_recall", "exc_f1", "evidence_retrieval_precision", "evidence_retrieval_recall", "evidence_retrieval_f1", "safe_auto_closure_rate", "unsafe_closure_rate", "correct_abstention_rate", "over_abstention_rate", "value_weighted_unsafe_closure_rate", "proof_complete_closure_rate", "right_answer_wrong_proof_rate", "auto_match_rate", "false_auto_match_rate"]:
        if metrics_a.get(key) is None or metrics_b.get(key) is None:
            if metrics_a.get(key) != metrics_b.get(key):
                assert False, f"{key} differs unexpectedly across fixed-seed runs"
        else:
            assert metrics_a[key] == metrics_b[key], f"{key} differs across fixed-seed runs"

    assert 0.0 <= metrics_a["evidence_retrieval_precision"] <= 1.0
    assert 0.0 <= metrics_a["evidence_retrieval_recall"] <= 1.0
    assert 0.0 <= metrics_a["evidence_retrieval_f1"] <= 1.0


def test_v2_1_json_after_timestamp_strip_is_identity_ready():
    from pathlib import Path

    path1 = Path("evaluation/results/final_evaluation_v2_1.json")
    if not path1.exists():
        pytest.skip("benchmark artifact not generated yet")

    with path1.open() as f:
        payload = json.load(f)
    stripped = _strip_volatile_fields(payload)

    assert "seed" in stripped
    assert stripped["seed"] == 4242
    assert 0.0 <= stripped["proof_metrics"]["evidence_citation_precision"] <= 1.0
    assert 0.0 <= stripped["proof_metrics"]["evidence_requirement_recall"] <= 1.0
