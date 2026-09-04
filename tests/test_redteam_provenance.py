import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from graph import ProvenanceGraph
from models import Order, Payment, Fee, Tax, Settlement, SettlementItem, BankTransaction
from reconciliation import ReconciliationEngine

now = datetime(2026, 8, 15, 12, 0, 0)
engine = ReconciliationEngine()

def make_clean_graph():
    g = ProvenanceGraph()
    amount = Decimal('100.00')
    fee_amt = Decimal('2.00')
    tax_amt = Decimal('0.36')
    expected = amount - fee_amt - tax_amt
    
    o = Order(order_id="1", customer_id="C1", amount=amount, currency="INR", created_at=now - timedelta(days=2), status="COMPLETED")
    p = Payment(payment_id="P1", order_id="1", amount=amount, currency="INR", status="CAPTURED", captured_at=now - timedelta(days=2, hours=-1), method="card")
    f = Fee(fee_id="F1", payment_id="P1", type="GATEWAY", amount=fee_amt, created_at=now - timedelta(days=2, hours=-1))
    t = Tax(tax_id="T1", payment_id="P1", type="GST", amount=tax_amt, created_at=now - timedelta(days=2, hours=-1))
    
    s = Settlement(settlement_id="S1", amount=expected, currency="INR", status="COMPLETED", initiated_at=now - timedelta(days=1), reference="UTR1")
    si = SettlementItem(item_id="SI1", settlement_id="S1", payment_id="P1", refund_id=None, amount=expected)
    b = BankTransaction(direction="CREDIT", bank_transaction_id="B1", amount=expected, currency="INR", timestamp=now, reference="UTR1")
    
    g.add_order(o)
    g.add_payment(p)
    g.add_fee(f)
    g.add_tax(t)
    g.add_settlement(s, [si])
    g.add_bank_transaction(b)
    g.link_bank_transaction_to_settlement("B1", "S1")
    return g

def test_missing_fee():
    g = make_clean_graph()
    g.g.remove_node("fee_F1")
    res = engine.reconcile_order(g.get_subgraph_for_order("1"), target_order_id="1", as_of_time=now)
    assert not res['decision'].startswith("RECONCILED")

def test_wrong_bank_reference():
    g = make_clean_graph()
    g.g.nodes["bank_tx_B1"]['data'].reference = "WRONG_UTR"
    res = engine.reconcile_order(g.get_subgraph_for_order("1"), target_order_id="1", as_of_time=now)
    assert not res['decision'].startswith("RECONCILED")

def test_future_bank_transaction():
    g = make_clean_graph()
    g.g.nodes["bank_tx_B1"]['data'].timestamp = now + timedelta(days=5)
    res = engine.reconcile_order(g.get_subgraph_for_order("1"), target_order_id="1", as_of_time=now)
    assert not res['decision'].startswith("RECONCILED")

def test_bank_before_settlement():
    g = make_clean_graph()
    g.g.nodes["bank_tx_B1"]['data'].timestamp = now - timedelta(days=1, hours=1)
    res = engine.reconcile_order(g.get_subgraph_for_order("1"), target_order_id="1", as_of_time=now)
    assert not res['decision'].startswith("RECONCILED")
