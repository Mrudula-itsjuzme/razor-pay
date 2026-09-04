import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from graph import ProvenanceGraph
from models import Order, Payment, Refund, Settlement, SettlementItem, BankTransaction
from reconciliation import ReconciliationEngine

now = datetime(2026, 8, 15, 12, 0, 0)
engine = ReconciliationEngine()

def test_refund_double_counting_fix():
    g = ProvenanceGraph()
    amount = Decimal('100.00')
    refund_amt = Decimal('20.00')
    expected = amount - refund_amt
    
    o = Order(order_id="1", customer_id="C1", amount=amount, currency="INR", created_at=now - timedelta(days=2), status="COMPLETED")
    p = Payment(payment_id="P1", order_id="1", amount=amount, currency="INR", status="CAPTURED", captured_at=now - timedelta(days=2, hours=-1), method="card")
    r = Refund(refund_id="R1", payment_id="P1", amount=refund_amt, currency="INR", status="PROCESSED", created_at=now - timedelta(days=2, hours=-1))
    
    # 1. Partial refund represented with EXPLICIT refund SettlementItem (Negative amount convention)
    s = Settlement(settlement_id="S1", amount=expected, currency="INR", status="COMPLETED", initiated_at=now - timedelta(days=1), reference="UTR1")
    si_p = SettlementItem(item_id="SI_P", settlement_id="S1", payment_id="P1", refund_id=None, amount=amount)
    si_r = SettlementItem(item_id="SI_R", settlement_id="S1", payment_id=None, refund_id="R1", amount=-refund_amt)
    b = BankTransaction(direction="CREDIT", bank_transaction_id="B1", amount=expected, currency="INR", timestamp=now, reference="UTR1")
    
    g.add_order(o)
    g.add_payment(p)
    g.add_refund(r)
    g.add_settlement(s, [si_p, si_r])
    g.add_bank_transaction(b)
    g.link_bank_transaction_to_settlement("B1", "S1")
    
    res = engine.reconcile_order(g.get_subgraph_for_order("1"), target_order_id="1", as_of_time=now)
    assert res['decision'].startswith("RECONCILED"), "Double counting of refunds when item is explicit must be fixed"

def test_refund_unitemized_convention():
    g = ProvenanceGraph()
    amount = Decimal('100.00')
    refund_amt = Decimal('20.00')
    expected = amount - refund_amt
    
    o = Order(order_id="2", customer_id="C2", amount=amount, currency="INR", created_at=now - timedelta(days=2), status="COMPLETED")
    p = Payment(payment_id="P2", order_id="2", amount=amount, currency="INR", status="CAPTURED", captured_at=now - timedelta(days=2, hours=-1), method="card")
    r = Refund(refund_id="R2", payment_id="P2", amount=refund_amt, currency="INR", status="PROCESSED", created_at=now - timedelta(days=2, hours=-1))
    
    # 2. Partial refund represented WITHOUT refund SettlementItem (Payment is gross, Settlement is net)
    s = Settlement(settlement_id="S2", amount=expected, currency="INR", status="COMPLETED", initiated_at=now - timedelta(days=1), reference="UTR2")
    si_p = SettlementItem(item_id="SI_P2", settlement_id="S2", payment_id="P2", refund_id=None, amount=amount)
    b = BankTransaction(direction="CREDIT", bank_transaction_id="B2", amount=expected, currency="INR", timestamp=now, reference="UTR2")
    
    g.add_order(o)
    g.add_payment(p)
    g.add_refund(r)
    g.add_settlement(s, [si_p])
    g.add_bank_transaction(b)
    g.link_bank_transaction_to_settlement("B2", "S2")
    
    res = engine.reconcile_order(g.get_subgraph_for_order("2"), target_order_id="2", as_of_time=now)
    assert res['decision'].startswith("RECONCILED"), "Must correctly deduct unitemized refund from gross payment"
