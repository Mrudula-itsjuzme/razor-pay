import sys
from decimal import Decimal
from datetime import datetime, timedelta
from graph import ProvenanceGraph
from models import Order, Payment, Fee, Tax, Settlement, SettlementItem, BankTransaction
from reconciliation import ReconciliationEngine

now = datetime(2026, 8, 15, 12, 0, 0)

def make_clean_graph():
    g = ProvenanceGraph()
    amount = Decimal('100.00')
    fee_amt = Decimal('2.00')
    tax_amt = Decimal('0.36')
    expected = amount - fee_amt - tax_amt
    
    o = Order("1", "C1", amount, "INR", now - timedelta(days=2), "COMPLETED")
    p = Payment("P1", "1", amount, "INR", "CAPTURED", now - timedelta(days=2, hours=-1))
    f = Fee("F1", "P1", "GATEWAY", fee_amt, now - timedelta(days=2, hours=-1))
    t = Tax("T1", "P1", "GST", tax_amt, now - timedelta(days=2, hours=-1))
    
    s = Settlement("S1", expected, "INR", "COMPLETED", now - timedelta(days=1), "UTR1")
    si = SettlementItem("SI1", "S1", "P1", None, expected)
    b = BankTransaction("B1", expected, "INR", now, "UTR1")
    
    g.add_order(o)
    g.add_payment(p)
    g.add_fee(f)
    g.add_tax(t)
    g.add_settlement(s, [si])
    g.add_bank_transaction(b)
    g.link_bank_transaction_to_settlement("B1", "S1")
    return g

engine = ReconciliationEngine()

def test_mutation():
    results = []
    
    # Baseline
    res = engine.reconcile_order(make_clean_graph().get_subgraph_for_order("1"), target_order_id="1", as_of_time=now)
    results.append(("Baseline", res['decision']))
    
    # Mutate 1: Remove Fee
    g = make_clean_graph()
    g.g.remove_node("fee_F1")
    res = engine.reconcile_order(g.get_subgraph_for_order("1"), target_order_id="1", as_of_time=now)
    results.append(("Remove Fee", res['decision']))
    
    # Mutate 2: Change bank reference
    g = make_clean_graph()
    g.g.nodes["bank_tx_B1"]['data'].reference = "WRONG_UTR"
    res = engine.reconcile_order(g.get_subgraph_for_order("1"), target_order_id="1", as_of_time=now)
    results.append(("Change Bank Ref", res['decision']))
    
    # Mutate 3: Future bank
    g = make_clean_graph()
    g.g.nodes["bank_tx_B1"]['data'].timestamp = now + timedelta(days=5)
    res = engine.reconcile_order(g.get_subgraph_for_order("1"), target_order_id="1", as_of_time=now)
    results.append(("Future Bank", res['decision']))
    
    for k, v in results:
        print(f"{k}: {v}")

test_mutation()
