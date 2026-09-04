import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from graph import ProvenanceGraph
from models import Order, Payment, Settlement, SettlementItem, BankTransaction
from reconciliation import ReconciliationEngine

now = datetime(2026, 8, 15, 12, 0, 0)
engine = ReconciliationEngine()

def test_missing_bank_inside_sla():
    g = ProvenanceGraph()
    amount = Decimal('100.00')
    o = Order(order_id="1", customer_id="C1", amount=amount, currency="INR", created_at=now - timedelta(days=2), status="COMPLETED")
    p = Payment(payment_id="P1", order_id="1", amount=amount, currency="INR", status="CAPTURED", captured_at=now - timedelta(days=2, hours=-1), method="card")
    s = Settlement(settlement_id="S1", amount=amount, currency="INR", status="COMPLETED", initiated_at=now - timedelta(days=1), reference="UTR1")
    si = SettlementItem(item_id="SI1", settlement_id="S1", payment_id="P1", refund_id=None, amount=amount)
    
    g.add_order(o)
    g.add_payment(p)
    g.add_settlement(s, [si])
    
    res = engine.reconcile_order(g.get_subgraph_for_order("1"), target_order_id="1", as_of_time=now)
    assert res['decision'] == "PENDING"
    assert res['evidence_contract'] == "PENDING_SETTLEMENT"

def test_missing_bank_outside_sla():
    g = ProvenanceGraph()
    amount = Decimal('100.00')
    o = Order(order_id="1", customer_id="C1", amount=amount, currency="INR", created_at=now - timedelta(days=10), status="COMPLETED")
    p = Payment(payment_id="P1", order_id="1", amount=amount, currency="INR", status="CAPTURED", captured_at=now - timedelta(days=10, hours=-1), method="card")
    # Settlement > 3 days old
    s = Settlement(settlement_id="S1", amount=amount, currency="INR", status="COMPLETED", initiated_at=now - timedelta(days=5), reference="UTR1")
    si = SettlementItem(item_id="SI1", settlement_id="S1", payment_id="P1", refund_id=None, amount=amount)
    
    g.add_order(o)
    g.add_payment(p)
    g.add_settlement(s, [si])
    
    res = engine.reconcile_order(g.get_subgraph_for_order("1"), target_order_id="1", as_of_time=now)
    assert res['decision'] == "ESCALATED"
    assert "SLA_BREACHED" in res['exception_details']['temporal_status']

def test_valid_evidence_outside_sla():
    g = ProvenanceGraph()
    amount = Decimal('100.00')
    o = Order(order_id="1", customer_id="C1", amount=amount, currency="INR", created_at=now - timedelta(days=10), status="COMPLETED")
    p = Payment(payment_id="P1", order_id="1", amount=amount, currency="INR", status="CAPTURED", captured_at=now - timedelta(days=10, hours=-1), method="card")
    s = Settlement(settlement_id="S1", amount=amount, currency="INR", status="COMPLETED", initiated_at=now - timedelta(days=5), reference="UTR1")
    si = SettlementItem(item_id="SI1", settlement_id="S1", payment_id="P1", refund_id=None, amount=amount)
    b = BankTransaction(direction="CREDIT", bank_transaction_id="B1", amount=amount, currency="INR", timestamp=now - timedelta(days=4), reference="UTR1")
    
    g.add_order(o)
    g.add_payment(p)
    g.add_settlement(s, [si])
    g.add_bank_transaction(b)
    g.link_bank_transaction_to_settlement("B1", "S1")
    
    res = engine.reconcile_order(g.get_subgraph_for_order("1"), target_order_id="1", as_of_time=now)
    assert res['decision'] == "RECONCILED", "SLA is for missing evidence, not an expiry date for valid proof"
