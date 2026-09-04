from datetime import datetime, timedelta
from decimal import Decimal
from models import Order, Payment, Fee, Tax, Settlement, SettlementItem, BankTransaction
from graph import ProvenanceGraph
from reconciliation import ReconciliationEngine

now = datetime(2026, 8, 15, 12, 0, 0)

def test_known_contradiction_missing_bank_inside_sla():
    engine = ReconciliationEngine()
    g = ProvenanceGraph()
    dt = now - timedelta(days=2) # Inside SLA
    amt = Decimal('100.00')
    o = Order(order_id='1', customer_id='C1', amount=amt, status='COMPLETED', created_at=dt)
    p = Payment(payment_id='P1', order_id='1', amount=amt, status='CAPTURED', method='card', captured_at=dt)
    
    # Missing bank tx! So it WOULD be PENDING...
    # BUT we have a known contradiction: Duplicate Payment!
    p2 = Payment(payment_id='P2', order_id='1', amount=amt, status='CAPTURED', method='card', captured_at=dt)
    
    s = Settlement(settlement_id='S1', amount=amt, status='COMPLETED', initiated_at=dt, reference='UTR1')
    si = SettlementItem(item_id='SI1', settlement_id='S1', payment_id='P1', amount=amt)
    
    g.add_order(o)
    g.add_payment(p)
    g.add_payment(p2)
    g.add_settlement(s, [si])
    
    res = engine.reconcile_order(g.get_subgraph_for_order('1'), target_order_id='1', as_of_time=now)
    assert res['decision'] == 'ESCALATED'

def test_wrong_provenance_missing_evidence():
    engine = ReconciliationEngine()
    g = ProvenanceGraph()
    dt = now - timedelta(days=2) # Inside SLA
    amt = Decimal('100.00')
    o = Order(order_id='1', customer_id='C1', amount=amt, status='COMPLETED', created_at=dt)
    p = Payment(payment_id='P1', order_id='1', amount=amt, status='CAPTURED', method='card', captured_at=dt)
    
    # Missing bank tx! So it WOULD be PENDING...
    # BUT wrong provenance: Settlement amount is 50, but SI is 100. Unexplained discrepancy!
    s = Settlement(settlement_id='S1', amount=Decimal('50.00'), status='COMPLETED', initiated_at=dt, reference='UTR1')
    si = SettlementItem(item_id='SI1', settlement_id='S1', payment_id='P1', amount=Decimal('100.00'))
    
    g.add_order(o)
    g.add_payment(p)
    g.add_settlement(s, [si])
    
    res = engine.reconcile_order(g.get_subgraph_for_order('1'), target_order_id='1', as_of_time=now)
    assert res['decision'] == 'ESCALATED'
    
def test_duplicate_reference_within_sla():
    engine = ReconciliationEngine()
    g = ProvenanceGraph()
    dt = now - timedelta(days=2) # Inside SLA
    amt = Decimal('100.00')
    o = Order(order_id='1', customer_id='C1', amount=amt, status='COMPLETED', created_at=dt)
    p = Payment(payment_id='P1', order_id='1', amount=amt, status='CAPTURED', method='card', captured_at=dt)
    
    s1 = Settlement(settlement_id='S1', amount=amt, status='COMPLETED', initiated_at=dt, reference='UTR_DUP')
    si1 = SettlementItem(item_id='SI1', settlement_id='S1', payment_id='P1', amount=amt)
    
    s2 = Settlement(settlement_id='S2', amount=amt, status='COMPLETED', initiated_at=dt, reference='UTR_DUP')
    b = BankTransaction(direction='CREDIT', bank_transaction_id='B1', amount=amt, timestamp=dt, reference='UTR_DUP')
    
    g.add_order(o)
    g.add_payment(p)
    g.add_settlement(s1, [si1])
    g.add_settlement(s2, [])
    g.add_bank_transaction(b)
    g.link_bank_transaction_to_settlement('B1', 'S1')
    g.link_bank_transaction_to_settlement('B1', 'S2')
    
    res = engine.reconcile_order(g.get_subgraph_for_order('1'), target_order_id='1', as_of_time=now)
    assert res['decision'] == 'ESCALATED'

