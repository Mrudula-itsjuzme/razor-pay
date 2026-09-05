from decimal import Decimal
from datetime import datetime, timedelta

import pytest

from graph import ProvenanceGraph
from models import BankTransaction, Fee, Order, Payment, Refund, Settlement, SettlementItem, Tax
from reconciliation import ReconciliationEngine

now = datetime(2026, 8, 15, 12, 0, 0)
engine = ReconciliationEngine()


def make_graph(order_id="O1", amount=Decimal("100.00"), settlement_amount=None, ref="UTR-01"):
    created_at = now - timedelta(days=3)
    payment_at = created_at + timedelta(hours=1)
    settlement_at = payment_at + timedelta(hours=2)
    g = ProvenanceGraph()
    order = Order(order_id=order_id, customer_id="C", amount=amount, currency="INR", created_at=created_at, status="COMPLETED")
    payment = Payment(payment_id=f"P{order_id}", order_id=order_id, amount=amount, currency="INR", status="CAPTURED", captured_at=payment_at, method="UPI")
    settlement = Settlement(settlement_id=f"S{order_id}", amount=settlement_amount or amount, currency="INR", status="COMPLETED", initiated_at=settlement_at, reference=ref)
    item = SettlementItem(item_id=f"SI{order_id}", settlement_id=f"S{order_id}", payment_id=f"P{order_id}", amount=amount, currency="INR")
    bank = BankTransaction(direction="CREDIT", bank_transaction_id=f"B{order_id}", amount=settlement_amount or amount, currency="INR", timestamp=settlement_at + timedelta(hours=1), reference=ref)
    g.add_order(order)
    g.add_payment(payment)
    g.add_settlement(settlement, [item])
    g.add_bank_transaction(bank)
    g.link_bank_transaction_to_settlement(f"B{order_id}", f"S{order_id}")
    return g


@pytest.mark.parametrize(
    "scenario, expected",
    [
        ("wrong_refund_attached_to_unrelated_payment", "reconciled"),
        ("wrong_fee_attached_to_unrelated_payment", "reconciled"),
        ("wrong_tax_attached_to_unrelated_payment", "reconciled"),
        ("unrelated_future_bank_lure", "reconciled"),
        ("unrelated_perfect_fee_lure", "reconciled"),
        ("unrelated_perfect_refund_lure", "reconciled"),
    ],
)
def test_provenance_adversarial_matrix(scenario, expected):
    if scenario == "same_amount_wrong_utr":
        g = make_graph(order_id="A1", amount=Decimal("100.00"), ref="UTR-REAL")
        wrong_tx = BankTransaction(direction="CREDIT", bank_transaction_id="BWRONG", amount=Decimal("100.00"), currency="INR", timestamp=now - timedelta(days=1), reference="UTR-FAKE")
        g.add_bank_transaction(wrong_tx)
        res = engine.reconcile_order(g.get_subgraph_for_order("A1"), target_order_id="A1", as_of_time=now)
    elif scenario == "same_amount_wrong_payment":
        g = make_graph(order_id="A2", amount=Decimal("100.00"), ref="UTR-2")
        wrong_payment = Payment(payment_id="PWRONG", order_id="OTHER", amount=Decimal("100.00"), currency="INR", status="CAPTURED", captured_at=now - timedelta(days=2, hours=1), method="UPI")
        g.add_payment(wrong_payment)
        res = engine.reconcile_order(g.get_subgraph_for_order("A2"), target_order_id="A2", as_of_time=now)
    elif scenario == "wrong_refund_attached_to_unrelated_payment":
        g = make_graph(order_id="A3", amount=Decimal("100.00"), ref="UTR-3")
        refund = Refund(refund_id="R-OUT", payment_id="P-OFF", amount=Decimal("20.00"), currency="INR", status="PROCESSED", created_at=now - timedelta(days=2))
        g.add_refund(refund)
        res = engine.reconcile_order(g.get_subgraph_for_order("A3"), target_order_id="A3", as_of_time=now)
    elif scenario == "wrong_fee_attached_to_unrelated_payment":
        g = make_graph(order_id="A4", amount=Decimal("100.00"), ref="UTR-4")
        fee = Fee(fee_id="F-OFF", payment_id="P-OFF", settlement_id=None, type="processing", amount=Decimal("2.00"), currency="INR", created_at=now - timedelta(days=2))
        g.add_fee(fee)
        res = engine.reconcile_order(g.get_subgraph_for_order("A4"), target_order_id="A4", as_of_time=now)
    elif scenario == "wrong_tax_attached_to_unrelated_payment":
        g = make_graph(order_id="A5", amount=Decimal("100.00"), ref="UTR-5")
        tax = Tax(tax_id="T-OFF", payment_id="P-OFF", settlement_id=None, type="gst", amount=Decimal("1.80"), currency="INR", created_at=now - timedelta(days=2))
        g.add_tax(tax)
        res = engine.reconcile_order(g.get_subgraph_for_order("A5"), target_order_id="A5", as_of_time=now)
    elif scenario == "duplicate_utr":
        g = make_graph(order_id="A6", amount=Decimal("100.00"), ref="SHARED-UTR")
        settlement2 = Settlement(settlement_id="S6B", amount=Decimal("100.00"), currency="INR", status="COMPLETED", initiated_at=now - timedelta(days=1), reference="SHARED-UTR")
        item2 = SettlementItem(item_id="SI6B", settlement_id="S6B", payment_id="P6B", amount=Decimal("100.00"), currency="INR")
        bank2 = BankTransaction(direction="CREDIT", bank_transaction_id="B6B", amount=Decimal("100.00"), currency="INR", timestamp=now - timedelta(days=1), reference="SHARED-UTR")
        g.add_settlement(settlement2, [item2])
        g.add_bank_transaction(bank2)
        g.link_bank_transaction_to_settlement("B6B", "S6B")
        res = engine.reconcile_order(g.get_subgraph_for_order("A6"), target_order_id="A6", as_of_time=now)
    elif scenario == "duplicate_bank_import":
        g = make_graph(order_id="A7", amount=Decimal("100.00"), ref="UTR-7")
        bank2 = BankTransaction(direction="CREDIT", bank_transaction_id="B7X", amount=Decimal("100.00"), currency="INR", timestamp=now - timedelta(days=1), reference="UTR-7")
        g.add_bank_transaction(bank2)
        res = engine.reconcile_order(g.get_subgraph_for_order("A7"), target_order_id="A7", as_of_time=now)
    elif scenario == "duplicate_payment":
        g = make_graph(order_id="A8", amount=Decimal("100.00"), ref="UTR-8")
        payment2 = Payment(payment_id="P8B", order_id="A8", amount=Decimal("100.00"), currency="INR", status="CAPTURED", captured_at=now - timedelta(days=2, hours=1), method="UPI")
        g.add_payment(payment2)
        res = engine.reconcile_order(g.get_subgraph_for_order("A8"), target_order_id="A8", as_of_time=now)
    elif scenario == "sibling_contamination_in_shared_settlement":
        g = make_graph(order_id="A9", amount=Decimal("100.00"), ref="UTR-9")
        sibling_payment = Payment(payment_id="P9SIB", order_id="OTHER", amount=Decimal("50.00"), currency="INR", status="CAPTURED", captured_at=now - timedelta(days=2), method="UPI")
        g.add_payment(sibling_payment)
        g.g.add_edge(f"payment_{sibling_payment.payment_id}", f"settlement_SA9", relation="INCLUDED_IN", amount=Decimal("50.00"))
        res = engine.reconcile_order(g.get_subgraph_for_order("A9"), target_order_id="A9", as_of_time=now)
    elif scenario == "many_to_many_settlement_collision":
        g = make_graph(order_id="A10", amount=Decimal("100.00"), ref="UTR-10")
        settlement2 = Settlement(settlement_id="S10B", amount=Decimal("100.00"), currency="INR", status="COMPLETED", initiated_at=now - timedelta(days=1), reference="UTR-10")
        item2 = SettlementItem(item_id="SI10B", settlement_id="S10B", payment_id="P10B", amount=Decimal("100.00"), currency="INR")
        bank2 = BankTransaction(direction="CREDIT", bank_transaction_id="B10B", amount=Decimal("100.00"), currency="INR", timestamp=now - timedelta(days=1), reference="UTR-10")
        g.add_settlement(settlement2, [item2])
        g.add_bank_transaction(bank2)
        g.link_bank_transaction_to_settlement("B10B", "S10B")
        res = engine.reconcile_order(g.get_subgraph_for_order("A10"), target_order_id="A10", as_of_time=now)
    elif scenario == "unrelated_future_bank_lure":
        g = make_graph(order_id="A11", amount=Decimal("100.00"), ref="UTR-11")
        future_lure = BankTransaction(direction="CREDIT", bank_transaction_id="B11FUT", amount=Decimal("100.00"), currency="INR", timestamp=now + timedelta(days=1), reference="UTR-OTHER")
        g.add_bank_transaction(future_lure)
        res = engine.reconcile_order(g.get_subgraph_for_order("A11"), target_order_id="A11", as_of_time=now)
    elif scenario == "unrelated_perfect_fee_lure":
        g = make_graph(order_id="A12", amount=Decimal("100.00"), ref="UTR-12")
        fee = Fee(fee_id="F-PERFECT", payment_id="P-OTHER", settlement_id=None, type="processing", amount=Decimal("2.00"), currency="INR", created_at=now - timedelta(days=2))
        g.add_fee(fee)
        res = engine.reconcile_order(g.get_subgraph_for_order("A12"), target_order_id="A12", as_of_time=now)
    elif scenario == "unrelated_perfect_refund_lure":
        g = make_graph(order_id="A13", amount=Decimal("100.00"), ref="UTR-13")
        refund = Refund(refund_id="R-PERFECT", payment_id="P-OTHER", amount=Decimal("20.00"), currency="INR", status="PROCESSED", created_at=now - timedelta(days=2))
        g.add_refund(refund)
        res = engine.reconcile_order(g.get_subgraph_for_order("A13"), target_order_id="A13", as_of_time=now)
    else:
        raise AssertionError(f"Missing case: {scenario}")

    if expected == "reconciled":
        assert res["decision"] == "RECONCILED"
    else:
        assert not res["decision"].startswith("RECONCILED")


@pytest.mark.parametrize(
    "case_name, order_id, amount, settlement_amount, extra, expected_decision",
    [
        ("zero_fee", "ZERO1", Decimal("100.00"), Decimal("100.00"), "zero_fee", "RECONCILED"),
        ("partial_refund", "PART1", Decimal("100.00"), Decimal("80.00"), "partial_refund", "RECONCILED"),
        ("multiple_partial_refunds", "MULT1", Decimal("100.00"), Decimal("70.00"), "multiple_partial_refunds", "RECONCILED"),
        ("over_refund", "OVER1", Decimal("100.00"), Decimal("90.00"), "over_refund", "ESCALATED"),
        ("one_paise_mismatch", "PAIS1", Decimal("100.00"), Decimal("100.01"), "one_paise_mismatch", "PENDING"),
        ("decimal_precision_boundary", "DEC1", Decimal("0.01"), Decimal("0.01"), "decimal_precision_boundary", "RECONCILED"),
        ("fee_plus_gst_identity", "FGST1", Decimal("100.00"), Decimal("97.64"), "fee_plus_gst_identity", "ESCALATED"),
        ("duplicate_fees", "DFEE1", Decimal("100.00"), Decimal("100.00"), "duplicate_fees", "PENDING"),
        ("duplicate_taxes", "DTAX1", Decimal("100.00"), Decimal("100.00"), "duplicate_taxes", "PENDING"),
        ("missing_fee", "MFEE1", Decimal("100.00"), Decimal("100.00"), "missing_fee", "RECONCILED"),
        ("contradictory_fee_values", "CONF1", Decimal("100.00"), Decimal("100.00"), "contradictory_fee_values", "PENDING"),
        ("settlement_amount_mismatch", "SMIS1", Decimal("100.00"), Decimal("120.00"), "settlement_amount_mismatch", "PENDING"),
    ],
)
def test_accounting_edge_case_matrix(case_name, order_id, amount, settlement_amount, extra, expected_decision):
    g = make_graph(order_id=order_id, amount=amount, settlement_amount=settlement_amount, ref=f"UTR-{case_name}")
    payment_id = f"P{order_id}"
    if case_name == "partial_refund":
        refund = Refund(refund_id="R1", payment_id=payment_id, amount=Decimal("20.00"), currency="INR", status="PROCESSED", created_at=now - timedelta(days=2))
        g.add_refund(refund)
    elif case_name == "multiple_partial_refunds":
        for idx, refund_amt in enumerate([Decimal("10.00"), Decimal("20.00")], start=1):
            refund = Refund(refund_id=f"R{idx}", payment_id=payment_id, amount=refund_amt, currency="INR", status="PROCESSED", created_at=now - timedelta(days=2, hours=idx))
            g.add_refund(refund)
    elif case_name == "over_refund":
        refund = Refund(refund_id="ROVER", payment_id=payment_id, amount=Decimal("150.00"), currency="INR", status="PROCESSED", created_at=now - timedelta(days=2))
        g.add_refund(refund)
    elif case_name == "zero_fee":
        g.add_fee(Fee(fee_id="FZERO", payment_id=payment_id, settlement_id=None, type="processing", amount=Decimal("0.00"), currency="INR", created_at=now - timedelta(days=2)))
    elif case_name == "duplicate_fees":
        g.add_fee(Fee(fee_id="F1", payment_id=payment_id, settlement_id=None, type="processing", amount=Decimal("2.00"), currency="INR", created_at=now - timedelta(days=2)))
        g.add_fee(Fee(fee_id="F2", payment_id=payment_id, settlement_id=None, type="processing", amount=Decimal("2.00"), currency="INR", created_at=now - timedelta(days=2)))
    elif case_name == "duplicate_taxes":
        g.add_tax(Tax(tax_id="T1", payment_id=payment_id, settlement_id=None, type="gst", amount=Decimal("1.80"), currency="INR", created_at=now - timedelta(days=2)))
        g.add_tax(Tax(tax_id="T2", payment_id=payment_id, settlement_id=None, type="gst", amount=Decimal("1.80"), currency="INR", created_at=now - timedelta(days=2)))
    elif case_name == "contradictory_fee_values":
        g.add_fee(Fee(fee_id="F3", payment_id=payment_id, settlement_id=None, type="processing", amount=Decimal("2.00"), currency="INR", created_at=now - timedelta(days=2)))
        g.add_fee(Fee(fee_id="F4", payment_id=payment_id, settlement_id=None, type="processing", amount=Decimal("4.00"), currency="INR", created_at=now - timedelta(days=2)))

    res = engine.reconcile_order(g.get_subgraph_for_order(order_id), target_order_id=order_id, as_of_time=now)
    if expected_decision == "RECONCILED":
        assert res["decision"] == "RECONCILED"
        assert res["proof_certificate"]["proof_completeness"] == 1.0
        required = res["proof_certificate"]["evidence_contract"]["required"]
        for req_type in required:
            assert any(slot["required_type"] == req_type and slot["satisfied"] for slot in res["proof_certificate"]["evidence_contract"]["evidence_slots"].values())
    else:
        assert res["decision"] in {"PENDING", "ESCALATED"}


def test_missing_fee_evidence_blocks_implied_deduction():
    g = make_graph(order_id="MISSINGFEE1", amount=Decimal("100.00"), settlement_amount=Decimal("97.64"), ref="UTR-MISSINGFEE")
    payment_id = "PMISSINGFEE1"
    g.add_tax(Tax(tax_id="T1", payment_id=payment_id, settlement_id=None, type="gst", amount=Decimal("0.36"), currency="INR", created_at=now - timedelta(days=2)))
    res = engine.reconcile_order(g.get_subgraph_for_order("MISSINGFEE1"), target_order_id="MISSINGFEE1", as_of_time=now)
    assert res["decision"] == "ESCALATED"
    assert res["proof_certificate"]["proof_completeness"] < 1.0


def test_explicit_zero_fee_is_not_missing_fee():
    g = make_graph(order_id="ZEROEXPLICIT", amount=Decimal("100.00"), settlement_amount=Decimal("100.00"), ref="UTR-ZEROEXPLICIT")
    payment_id = "PZEROEXPLICIT"
    g.add_fee(Fee(fee_id="FZERO", payment_id=payment_id, settlement_id=None, type="processing", amount=Decimal("0.00"), currency="INR", created_at=now - timedelta(days=2)))
    res = engine.reconcile_order(g.get_subgraph_for_order("ZEROEXPLICIT"), target_order_id="ZEROEXPLICIT", as_of_time=now)
    assert res["decision"] == "RECONCILED"
    assert res["proof_certificate"]["proof_completeness"] == 1.0


def test_shared_settlement_graph_contamination():
    g = make_graph(order_id="SHAR1", amount=Decimal("100.00"), ref="UTR-SH")
    sibling = Payment(payment_id="P-SIB", order_id="OTHER", amount=Decimal("100.00"), currency="INR", status="CAPTURED", captured_at=now - timedelta(days=2), method="UPI")
    g.add_payment(sibling)
    g.g.add_edge("payment_P-SIB", "settlement_SSHAR1", relation="INCLUDED_IN", amount=Decimal("100.00"))
    res = engine.reconcile_order(g.get_subgraph_for_order("SHAR1"), target_order_id="SHAR1", as_of_time=now)
    assert not res["decision"].startswith("RECONCILED")


def test_missing_bank_closure_bypass():
    g = make_graph(order_id="MISS1", amount=Decimal("100.00"), ref="UTR-MB")
    g.g.remove_node("bank_tx_BMISS1")
    res = engine.reconcile_order(g.get_subgraph_for_order("MISS1"), target_order_id="MISS1", as_of_time=now)
    assert res["decision"] in {"PENDING", "ESCALATED"}


def test_ai_authority_bypass():
    g = make_graph(order_id="AUB1", amount=Decimal("100.00"), ref="UTR-AU")
    g.g.remove_node("bank_tx_BAUB1")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("reconciliation.analyze_exception", lambda *args, **kwargs: {"recommended_action": "RECONCILED_FIXED_ACCOUNTING", "hypotheses": ["missing evidence"], "confidence": "0.99"})
        res = engine.reconcile_order(g.get_subgraph_for_order("AUB1"), target_order_id="AUB1", as_of_time=now, max_layer=4)
    assert res["decision"] in {"PENDING", "ESCALATED"}
    assert res["decision_authority"] != "DETERMINISTIC"


def test_temporal_causality_bypass():
    g = make_graph(order_id="TIME1", amount=Decimal("100.00"), ref="UTR-TM")
    g.g.nodes["order_TIME1"]["data"].created_at = now + timedelta(days=1)
    res = engine.reconcile_order(g.get_subgraph_for_order("TIME1"), target_order_id="TIME1", as_of_time=now)
    assert res["proof_validity"] == "FAIL"
    assert not res["decision"].startswith("RECONCILED")


def test_duplicate_utr_double_spend():
    g = make_graph(order_id="DUP1", amount=Decimal("100.00"), ref="UTR-dup")
    bank2 = BankTransaction(direction="CREDIT", bank_transaction_id="B2DUP", amount=Decimal("100.00"), currency="INR", timestamp=now - timedelta(hours=2), reference="UTR-dup")
    g.add_bank_transaction(bank2)
    g.link_bank_transaction_to_settlement("B2DUP", "SDUP1")
    res = engine.reconcile_order(g.get_subgraph_for_order("DUP1"), target_order_id="DUP1", as_of_time=now)
    assert not res["decision"].startswith("RECONCILED")


def test_refund_double_counting():
    g = make_graph(order_id="REF1", amount=Decimal("100.00"), ref="UTR-REF")
    refund = Refund(refund_id="RREF1", payment_id="PREF1", amount=Decimal("20.00"), currency="INR", status="PROCESSED", created_at=now - timedelta(days=2))
    g.add_refund(refund)
    res = engine.reconcile_order(g.get_subgraph_for_order("REF1"), target_order_id="REF1", as_of_time=now)
    assert res["decision"] == "RECONCILED"


def test_wrong_refund_provenance():
    g = make_graph(order_id="WRF1", amount=Decimal("100.00"), ref="UTR-WR")
    refund = Refund(refund_id="RWRONG", payment_id="POTHER", amount=Decimal("50.00"), currency="INR", status="PROCESSED", created_at=now - timedelta(days=2))
    g.add_refund(refund)
    res = engine.reconcile_order(g.get_subgraph_for_order("WRF1"), target_order_id="WRF1", as_of_time=now)
    assert res["decision"] == "RECONCILED"


def test_type_based_proof_completeness_bug():
    g = make_graph(order_id="TYPE1", amount=Decimal("100.00"), ref="UTR-TYPE")
    res = engine.reconcile_order(g.get_subgraph_for_order("TYPE1"), target_order_id="TYPE1", as_of_time=now)
    assert res["proof_certificate"]["evidence_contract"]["required"] == ["Payment", "Settlement", "BankTransaction"]
    assert "Fee" not in res["proof_certificate"]["evidence_contract"]["required"]


def test_sibling_contamination():
    g = make_graph(order_id="SIB1", amount=Decimal("100.00"), ref="UTR-SIB")
    sibling = Payment(payment_id="PSIBX", order_id="OTHER", amount=Decimal("60.00"), currency="INR", status="CAPTURED", captured_at=now - timedelta(days=2), method="UPI")
    g.add_payment(sibling)
    g.g.add_edge("payment_PSIBX", "settlement_SSIB1", relation="INCLUDED_IN", amount=Decimal("60.00"))
    res = engine.reconcile_order(g.get_subgraph_for_order("SIB1"), target_order_id="SIB1", as_of_time=now)
    assert not res["decision"].startswith("RECONCILED")


def test_benchmark_timestamp_lure_inconsistency():
    g = make_graph(order_id="LURE1", amount=Decimal("100.00"), ref="UTR-LURE")
    future_tx = BankTransaction(direction="CREDIT", bank_transaction_id="BLURE", amount=Decimal("100.00"), currency="INR", timestamp=now + timedelta(days=3), reference="UTR-LURE")
    g.add_bank_transaction(future_tx)
    g.link_bank_transaction_to_settlement("BLURE", "SLURE1")
    res = engine.reconcile_order(g.get_subgraph_for_order("LURE1"), target_order_id="LURE1", as_of_time=now)
    assert res["proof_validity"] == "FAIL"
