import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from graph import ProvenanceGraph
from models import Order, Payment, Fee, Tax, Settlement, SettlementItem, BankTransaction
from reconciliation import ReconciliationEngine

now = datetime(2026, 8, 15, 12, 0, 0)
engine = ReconciliationEngine()

def test_shared_settlement_contamination():
    g = ProvenanceGraph()
    amount = Decimal('100.00')
    fee_amt = Decimal('2.00')
    tax_amt = Decimal('0.36')
    expected = amount - fee_amt - tax_amt
    
    o_a = Order(order_id="A", customer_id="C1", amount=amount, currency="INR", created_at=now - timedelta(days=2), status="COMPLETED")
    p_a = Payment(payment_id="P_A", order_id="A", amount=amount, currency="INR", status="CAPTURED", captured_at=now - timedelta(days=2, hours=-1), method="card")
    f_a = Fee(fee_id="F_A", payment_id="P_A", type="GATEWAY", amount=fee_amt, created_at=now - timedelta(days=2, hours=-1))
    t_a = Tax(tax_id="T_A", payment_id="P_A", type="GST", amount=tax_amt, created_at=now - timedelta(days=2, hours=-1))
    
    o_b = Order(order_id="B", customer_id="C2", amount=amount, currency="INR", created_at=now - timedelta(days=2), status="COMPLETED")
    p_b = Payment(payment_id="P_B", order_id="B", amount=amount, currency="INR", status="CAPTURED", captured_at=now - timedelta(days=2, hours=-1), method="card")
    t_b = Tax(tax_id="T_B", payment_id="P_B", type="GST", amount=tax_amt, created_at=now - timedelta(days=2, hours=-1))
    
    s = Settlement(settlement_id="S1", amount=expected * 2, currency="INR", status="COMPLETED", initiated_at=now - timedelta(days=1), reference="UTR1")
    si_a = SettlementItem(item_id="SI_A", settlement_id="S1", payment_id="P_A", refund_id=None, amount=expected)
    si_b = SettlementItem(item_id="SI_B", settlement_id="S1", payment_id="P_B", refund_id=None, amount=expected)
    b = BankTransaction(direction="CREDIT", bank_transaction_id="B1", amount=expected * 2, currency="INR", timestamp=now, reference="UTR1")
    
    g.add_order(o_a)
    g.add_payment(p_a)
    g.add_fee(f_a)
    g.add_tax(t_a)
    
    g.add_order(o_b)
    g.add_payment(p_b)
    g.add_tax(t_b)
    
    g.add_settlement(s, [si_a, si_b])
    g.add_bank_transaction(b)
    g.link_bank_transaction_to_settlement("B1", "S1")
    
    res_a = engine.reconcile_order(g.get_subgraph_for_order("A"), target_order_id="A", as_of_time=now)
    res_b = engine.reconcile_order(g.get_subgraph_for_order("B"), target_order_id="B", as_of_time=now)
    
    assert res_a['decision'].startswith("RECONCILED"), "Valid order should be reconciled despite shared settlement"
    assert not res_b['decision'].startswith("RECONCILED"), "Invalid order should not be reconciled"
