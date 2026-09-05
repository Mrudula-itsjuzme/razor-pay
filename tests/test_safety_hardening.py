from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from graph import ProvenanceGraph
from models import BankTransaction, Order, Payment, Settlement, SettlementItem
from reconciliation import ReconciliationEngine

now = datetime(2026, 8, 15, 12, 0, 0)
engine = ReconciliationEngine()


def make_valid_graph(order_id="O1", amount=Decimal("100.00"), reference="UTR1"):
    created_at = now - timedelta(days=3)
    payment_at = created_at + timedelta(hours=1)
    settlement_at = payment_at + timedelta(hours=2)
    bank_at = settlement_at + timedelta(hours=1)

    g = ProvenanceGraph()
    order = Order(
        order_id=order_id,
        customer_id="C1",
        amount=amount,
        currency="INR",
        created_at=created_at,
        status="COMPLETED",
    )
    payment = Payment(
        payment_id=f"P{order_id}",
        order_id=order_id,
        amount=amount,
        currency="INR",
        captured_at=payment_at,
        status="CAPTURED",
        method="UPI",
    )
    settlement = Settlement(
        settlement_id=f"S{order_id}",
        amount=amount,
        currency="INR",
        status="COMPLETED",
        initiated_at=settlement_at,
        reference=reference,
    )
    item = SettlementItem(
        item_id=f"SI{order_id}",
        settlement_id=f"S{order_id}",
        payment_id=f"P{order_id}",
        refund_id=None,
        amount=amount,
        currency="INR",
    )
    bank = BankTransaction(
        direction="CREDIT",
        bank_transaction_id=f"B{order_id}",
        amount=amount,
        currency="INR",
        timestamp=bank_at,
        reference=reference,
    )

    g.add_order(order)
    g.add_payment(payment)
    g.add_settlement(settlement, [item])
    g.add_bank_transaction(bank)
    g.link_bank_transaction_to_settlement(f"B{order_id}", f"S{order_id}")
    return g


def test_ai_output_cannot_authorize_closure():
    g = make_valid_graph(order_id="AI1")
    subgraph = g.get_subgraph_for_order("AI1")
    with patch("reconciliation.analyze_exception") as mock_analyze:
        mock_analyze.return_value = {
            "recommended_action": "RECONCILED_FIXED_ACCOUNTING",
            "likely_causes": ["AI forced reconciliation"],
            "hypotheses": ["missing required evidence"],
        }
        res = engine.reconcile_order(subgraph, target_order_id="AI1", as_of_time=now, max_layer=4)
    assert res["decision"] == "RECONCILED"
    assert res["decision_authority"] == "DETERMINISTIC"


def test_ai_exception_text_cannot_alter_deterministic_state():
    g = make_valid_graph(order_id="AI2")
    subgraph = g.get_subgraph_for_order("AI2")
    with patch("reconciliation.analyze_exception") as mock_analyze:
        mock_analyze.return_value = {
            "recommended_action": "RECONCILED",
            "confidence": "0.99",
            "supported_hypotheses": ["Force closure"],
            "hypotheses": ["Force closure"],
        }
        res = engine.reconcile_order(subgraph, target_order_id="AI2", as_of_time=now, max_layer=4)
    assert res["decision"] == "RECONCILED"
    assert res["decision_authority"] == "DETERMINISTIC"


def test_model_failure_preserves_deterministic_decision():
    g = make_valid_graph(order_id="AI3")
    subgraph = g.get_subgraph_for_order("AI3")
    with patch("reconciliation.analyze_exception", side_effect=RuntimeError("AI unavailable")):
        res = engine.reconcile_order(subgraph, target_order_id="AI3", as_of_time=now, max_layer=4)
    assert res["decision"] == "RECONCILED"
    assert res["decision_authority"] == "DETERMINISTIC"


def test_contradiction_blocks_closure():
    g = ProvenanceGraph()
    created_at = now - timedelta(days=3)
    payment_at = created_at + timedelta(hours=1)
    settlement_at = payment_at + timedelta(hours=2)
    order = Order(order_id="C1", customer_id="cust", amount=Decimal("100.00"), currency="INR", created_at=created_at, status="COMPLETED")
    payment = Payment(payment_id="P1", order_id="C1", amount=Decimal("100.00"), currency="INR", status="CAPTURED", captured_at=payment_at, method="UPI")
    settlement = Settlement(settlement_id="S1", amount=Decimal("100.00"), currency="INR", status="COMPLETED", initiated_at=settlement_at, reference="UTR-1")
    item = SettlementItem(item_id="SI1", settlement_id="S1", payment_id="P1", amount=Decimal("100.00"), currency="INR")
    bank_a = BankTransaction(direction="CREDIT", bank_transaction_id="B1", amount=Decimal("100.00"), currency="INR", timestamp=settlement_at + timedelta(hours=1), reference="UTR-1")
    bank_b = BankTransaction(direction="CREDIT", bank_transaction_id="B2", amount=Decimal("100.00"), currency="INR", timestamp=settlement_at + timedelta(hours=1), reference="UTR-1")

    g.add_order(order)
    g.add_payment(payment)
    g.add_settlement(settlement, [item])
    g.add_bank_transaction(bank_a)
    g.add_bank_transaction(bank_b)
    g.link_bank_transaction_to_settlement("B1", "S1")
    g.link_bank_transaction_to_settlement("B2", "S1")

    res = engine.reconcile_order(g.get_subgraph_for_order("C1"), target_order_id="C1", as_of_time=now)
    assert not res["decision"].startswith("RECONCILED")
    assert res["proof_validity"] == "FAIL"


def test_missing_required_evidence_blocks_closure():
    g = ProvenanceGraph()
    created_at = now - timedelta(days=3)
    payment_at = created_at + timedelta(hours=1)
    settlement_at = payment_at + timedelta(hours=2)
    order = Order(order_id="M1", customer_id="cust", amount=Decimal("100.00"), currency="INR", created_at=created_at, status="COMPLETED")
    payment = Payment(payment_id="P_M1", order_id="M1", amount=Decimal("100.00"), currency="INR", status="CAPTURED", captured_at=payment_at, method="UPI")
    settlement = Settlement(settlement_id="S_M1", amount=Decimal("100.00"), currency="INR", status="COMPLETED", initiated_at=settlement_at, reference="UTR_M1")
    item = SettlementItem(item_id="SI_M1", settlement_id="S_M1", payment_id="P_M1", amount=Decimal("100.00"), currency="INR")

    g.add_order(order)
    g.add_payment(payment)
    g.add_settlement(settlement, [item])

    res = engine.reconcile_order(g.get_subgraph_for_order("M1"), target_order_id="M1", as_of_time=now)
    assert not res["decision"].startswith("RECONCILED")
    assert res["decision"] in {"PENDING", "ESCALATED"}
    required = res["proof_certificate"]["evidence_contract"]["required"]
    assert "Payment" in required and "Settlement" in required
    assert "BankTransaction" not in required


def test_hypothesis_cannot_become_observed_evidence():
    g = make_valid_graph(order_id="H1")
    invalid = g.get_subgraph_for_order("H1")
    with patch("reconciliation.analyze_exception") as mock:
        mock.return_value = {
            "recommended_action": "RECONCILED_FIXED_ACCOUNTING",
            "supported_hypotheses": ["Missing fee"],
            "unsupported_hypotheses": ["Missing fee"],
            "hypotheses": ["Missing fee"],
        }
        res = engine.reconcile_order(invalid, target_order_id="H1", as_of_time=now, max_layer=4)
    certificate = str(res["proof_certificate"])
    assert "Missing fee" not in certificate
    assert "hypotheses" not in str(res["proof_certificate"])


def test_within_sla_pending_behavior():
    g = ProvenanceGraph()
    created_at = now - timedelta(days=5)
    payment_at = created_at + timedelta(hours=1)
    settlement_at = now - timedelta(days=1)
    order = Order(order_id="P1", customer_id="cust", amount=Decimal("100.00"), currency="INR", created_at=created_at, status="COMPLETED")
    payment = Payment(payment_id="PP1", order_id="P1", amount=Decimal("100.00"), currency="INR", status="CAPTURED", captured_at=payment_at, method="UPI")
    settlement = Settlement(settlement_id="PS1", amount=Decimal("100.00"), currency="INR", status="COMPLETED", initiated_at=settlement_at, reference="UTR-P1")
    item = SettlementItem(item_id="PSI1", settlement_id="PS1", payment_id="PP1", amount=Decimal("100.00"), currency="INR")
    g.add_order(order)
    g.add_payment(payment)
    g.add_settlement(settlement, [item])
    res = engine.reconcile_order(g.get_subgraph_for_order("P1"), target_order_id="P1", as_of_time=now)
    assert res["decision"] == "PENDING"
    assert res["evidence_contract"] == "PENDING_SETTLEMENT"


def test_exact_sla_boundary_behavior():
    g = ProvenanceGraph()
    created_at = now - timedelta(days=5)
    payment_at = created_at + timedelta(hours=1)
    settlement_at = now - timedelta(days=3)
    order = Order(order_id="P2", customer_id="cust", amount=Decimal("100.00"), currency="INR", created_at=created_at, status="COMPLETED")
    payment = Payment(payment_id="PP2", order_id="P2", amount=Decimal("100.00"), currency="INR", status="CAPTURED", captured_at=payment_at, method="UPI")
    settlement = Settlement(settlement_id="PS2", amount=Decimal("100.00"), currency="INR", status="COMPLETED", initiated_at=settlement_at, reference="UTR-P2")
    item = SettlementItem(item_id="PSI2", settlement_id="PS2", payment_id="PP2", amount=Decimal("100.00"), currency="INR")
    g.add_order(order)
    g.add_payment(payment)
    g.add_settlement(settlement, [item])
    res = engine.reconcile_order(g.get_subgraph_for_order("P2"), target_order_id="P2", as_of_time=now)
    assert res["decision"] == "PENDING"


def test_after_sla_escalates():
    g = ProvenanceGraph()
    created_at = now - timedelta(days=10)
    payment_at = created_at + timedelta(hours=1)
    settlement_at = now - timedelta(days=5)
    order = Order(order_id="P3", customer_id="cust", amount=Decimal("100.00"), currency="INR", created_at=created_at, status="COMPLETED")
    payment = Payment(payment_id="PP3", order_id="P3", amount=Decimal("100.00"), currency="INR", status="CAPTURED", captured_at=payment_at, method="UPI")
    settlement = Settlement(settlement_id="PS3", amount=Decimal("100.00"), currency="INR", status="COMPLETED", initiated_at=settlement_at, reference="UTR-P3")
    item = SettlementItem(item_id="PSI3", settlement_id="PS3", payment_id="PP3", amount=Decimal("100.00"), currency="INR")
    g.add_order(order)
    g.add_payment(payment)
    g.add_settlement(settlement, [item])
    res = engine.reconcile_order(g.get_subgraph_for_order("P3"), target_order_id="P3", as_of_time=now)
    assert res["decision"] == "ESCALATED"


def test_future_evidence_cannot_close():
    g = ProvenanceGraph()
    created_at = now - timedelta(days=3)
    payment_at = created_at + timedelta(hours=1)
    settlement_at = payment_at + timedelta(hours=2)
    order = Order(order_id="F1", customer_id="cust", amount=Decimal("100.00"), currency="INR", created_at=created_at, status="COMPLETED")
    payment = Payment(payment_id="PF1", order_id="F1", amount=Decimal("100.00"), currency="INR", status="CAPTURED", captured_at=payment_at, method="UPI")
    settlement = Settlement(settlement_id="FS1", amount=Decimal("100.00"), currency="INR", status="COMPLETED", initiated_at=settlement_at, reference="UTR-F1")
    item = SettlementItem(item_id="FSI1", settlement_id="FS1", payment_id="PF1", amount=Decimal("100.00"), currency="INR")
    bank = BankTransaction(direction="CREDIT", bank_transaction_id="BF1", amount=Decimal("100.00"), currency="INR", timestamp=now + timedelta(hours=1), reference="UTR-F1")
    g.add_order(order)
    g.add_payment(payment)
    g.add_settlement(settlement, [item])
    g.add_bank_transaction(bank)
    g.link_bank_transaction_to_settlement("BF1", "FS1")
    res = engine.reconcile_order(g.get_subgraph_for_order("F1"), target_order_id="F1", as_of_time=now)
    assert res["decision"] != "RECONCILED"
    assert res["proof_validity"] == "FAIL"


def test_late_valid_evidence_can_resolve_pending():
    g = ProvenanceGraph()
    created_at = now - timedelta(days=10)
    payment_at = created_at + timedelta(hours=1)
    settlement_at = now - timedelta(days=2)
    order = Order(order_id="L1", customer_id="cust", amount=Decimal("100.00"), currency="INR", created_at=created_at, status="COMPLETED")
    payment = Payment(payment_id="PL1", order_id="L1", amount=Decimal("100.00"), currency="INR", status="CAPTURED", captured_at=payment_at, method="UPI")
    settlement = Settlement(settlement_id="LS1", amount=Decimal("100.00"), currency="INR", status="COMPLETED", initiated_at=settlement_at, reference="UTR-L1")
    item = SettlementItem(item_id="LSI1", settlement_id="LS1", payment_id="PL1", amount=Decimal("100.00"), currency="INR")
    bank = BankTransaction(direction="CREDIT", bank_transaction_id="BL1", amount=Decimal("100.00"), currency="INR", timestamp=now - timedelta(hours=1), reference="UTR-L1")
    g.add_order(order)
    g.add_payment(payment)
    g.add_settlement(settlement, [item])
    g.add_bank_transaction(bank)
    g.link_bank_transaction_to_settlement("BL1", "LS1")
    res = engine.reconcile_order(g.get_subgraph_for_order("L1"), target_order_id="L1", as_of_time=now)
    assert res["decision"] == "RECONCILED"


def test_delayed_settlement_behavior():
    g = ProvenanceGraph()
    created_at = now - timedelta(days=5)
    payment_at = created_at + timedelta(hours=1)
    settlement_at = now - timedelta(days=4)
    order = Order(order_id="D1", customer_id="cust", amount=Decimal("100.00"), currency="INR", created_at=created_at, status="COMPLETED")
    payment = Payment(payment_id="PD1", order_id="D1", amount=Decimal("100.00"), currency="INR", status="CAPTURED", captured_at=payment_at, method="UPI")
    settlement = Settlement(settlement_id="DS1", amount=Decimal("100.00"), currency="INR", status="COMPLETED", initiated_at=settlement_at, reference="UTR-D1")
    item = SettlementItem(item_id="DSI1", settlement_id="DS1", payment_id="PD1", amount=Decimal("100.00"), currency="INR")
    g.add_order(order)
    g.add_payment(payment)
    g.add_settlement(settlement, [item])
    res = engine.reconcile_order(g.get_subgraph_for_order("D1"), target_order_id="D1", as_of_time=now)
    assert res["decision"] in {"PENDING", "ESCALATED"}
