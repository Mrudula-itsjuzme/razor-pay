from datetime import datetime, timedelta
from decimal import Decimal
from models import Order, Payment, Fee, Tax, Settlement, SettlementItem, BankTransaction
from graph import ProvenanceGraph
from reconciliation import ReconciliationEngine

now = datetime(2026, 8, 15, 12, 0, 0)

def test_duplicate_utr_unsafe_closure():
    engine = ReconciliationEngine()
    g = ProvenanceGraph()
    dt = now - timedelta(days=2)
    amt = Decimal('100.00')
    o = Order(order_id='1', customer_id='C1', amount=amt, status='COMPLETED', created_at=dt)
    p = Payment(payment_id='P1', order_id='1', amount=amt, status='CAPTURED', method='card', captured_at=dt)
    s1 = Settlement(settlement_id='S1', amount=amt, status='COMPLETED', initiated_at=dt, reference='UTR_DUP')
    si1 = SettlementItem(item_id='SI1', settlement_id='S1', payment_id='P1', amount=amt)
    
    # Unrelated settlement with same UTR
    s2 = Settlement(settlement_id='S2', amount=amt, status='COMPLETED', initiated_at=dt, reference='UTR_DUP')
    
    # Only one bank tx with that UTR
    b = BankTransaction(direction='CREDIT', bank_transaction_id='B1', amount=amt, timestamp=dt, reference='UTR_DUP')
    
    g.add_order(o)
    g.add_payment(p)
    g.add_settlement(s1, [si1])
    g.add_settlement(s2, [])
    g.add_bank_transaction(b)
    g.link_bank_transaction_to_settlement('B1', 'S1')
    g.link_bank_transaction_to_settlement('B1', 'S2')
    
    res = engine.reconcile_order(g.get_subgraph_for_order('1'), target_order_id='1', as_of_time=now)
    # Must not be RECONCILED
    assert res['decision'] in ['PENDING', 'ESCALATED']
    assert not res.get('exception_details', {}).get('closure_authorized', False)

def test_wrong_refund_perfect_arithmetic():
    engine = ReconciliationEngine()
    g = ProvenanceGraph()
    dt = now - timedelta(days=2)
    amt = Decimal('100.00')
    o = Order(order_id='1', customer_id='C1', amount=amt, status='COMPLETED', created_at=dt)
    p = Payment(payment_id='P1', order_id='1', amount=amt, status='CAPTURED', method='card', captured_at=dt)
    
    # Missing Fee, but a wrong refund makes up for it perfectly
    # The refund belongs to a different payment
    import models
    r = models.Refund(refund_id='R1', payment_id='P_OTHER', amount=Decimal('2.00'), status='PROCESSED', created_at=dt)
    
    s = Settlement(settlement_id='S1', amount=Decimal('98.00'), status='COMPLETED', initiated_at=dt, reference='UTR1')
    si = SettlementItem(item_id='SI1', settlement_id='S1', payment_id='P1', amount=amt)
    b = BankTransaction(direction='CREDIT', bank_transaction_id='B1', amount=Decimal('98.00'), timestamp=dt, reference='UTR1')
    
    g.add_order(o)
    g.add_payment(p)
    g.add_refund(r)
    g.add_settlement(s, [si])
    g.add_bank_transaction(b)
    g.link_bank_transaction_to_settlement('B1', 'S1')
    
    res = engine.reconcile_order(g.get_subgraph_for_order('1'), target_order_id='1', as_of_time=now)
    assert res['decision'] in ['PENDING', 'ESCALATED']
    
def test_future_bank_temporal_gate():
    engine = ReconciliationEngine()
    g = ProvenanceGraph()
    dt = now - timedelta(days=2)
    amt = Decimal('100.00')
    o = Order(order_id='1', customer_id='C1', amount=amt, status='COMPLETED', created_at=dt)
    p = Payment(payment_id='P1', order_id='1', amount=amt, status='CAPTURED', method='card', captured_at=dt)
    s = Settlement(settlement_id='S1', amount=amt, status='COMPLETED', initiated_at=dt, reference='UTR1')
    si = SettlementItem(item_id='SI1', settlement_id='S1', payment_id='P1', amount=amt)
    
    # Future bank
    b = BankTransaction(direction='CREDIT', bank_transaction_id='B1', amount=amt, timestamp=now + timedelta(days=1), reference='UTR1')
    
    g.add_order(o)
    g.add_payment(p)
    g.add_settlement(s, [si])
    g.add_bank_transaction(b)
    g.link_bank_transaction_to_settlement('B1', 'S1')
    
    res = engine.reconcile_order(g.get_subgraph_for_order('1'), target_order_id='1', as_of_time=now)
    assert res['decision'] == 'ESCALATED'
    assert not res.get('exception_details', {}).get('closure_authorized', False)
    assert res['proof_certificate']['temporal_checks'] == 'FAIL'
    
def test_complete_old_evidence_sla_semantics():
    engine = ReconciliationEngine()
    g = ProvenanceGraph()
    dt = now - timedelta(days=10) # Older than SLA!
    amt = Decimal('100.00')
    o = Order(order_id='1', customer_id='C1', amount=amt, status='COMPLETED', created_at=dt)
    p = Payment(payment_id='P1', order_id='1', amount=amt, status='CAPTURED', method='card', captured_at=dt)
    s = Settlement(settlement_id='S1', amount=amt, status='COMPLETED', initiated_at=dt, reference='UTR1')
    si = SettlementItem(item_id='SI1', settlement_id='S1', payment_id='P1', amount=amt)
    b = BankTransaction(direction='CREDIT', bank_transaction_id='B1', amount=amt, timestamp=dt, reference='UTR1')
    
    g.add_order(o)
    g.add_payment(p)
    g.add_settlement(s, [si])
    g.add_bank_transaction(b)
    g.link_bank_transaction_to_settlement('B1', 'S1')
    
    res = engine.reconcile_order(g.get_subgraph_for_order('1'), target_order_id='1', as_of_time=now)
    assert res['decision'] == 'RECONCILED'
    assert res['proof_certificate']['temporal_checks'] == 'PASS'
    
def test_wrong_bank_does_not_complete_contract():
    engine = ReconciliationEngine()
    g = ProvenanceGraph()
    dt = now - timedelta(days=2)
    amt = Decimal('100.00')
    o = Order(order_id='1', customer_id='C1', amount=amt, status='COMPLETED', created_at=dt)
    p = Payment(payment_id='P1', order_id='1', amount=amt, status='CAPTURED', method='card', captured_at=dt)
    s = Settlement(settlement_id='S1', amount=amt, status='COMPLETED', initiated_at=dt, reference='UTR1')
    si = SettlementItem(item_id='SI1', settlement_id='S1', payment_id='P1', amount=amt)
    
    # Wrong bank reference, future dated so it fails temporal gate and cannot fallback to PENDING
    b = BankTransaction(direction='CREDIT', bank_transaction_id='B1', amount=amt, timestamp=now + timedelta(days=1), reference='UTR_WRONG')
    
    g.add_order(o)
    g.add_payment(p)
    g.add_settlement(s, [si])
    g.add_bank_transaction(b)
    g.link_bank_transaction_to_settlement('B1', 'S1')
    
    res = engine.reconcile_order(g.get_subgraph_for_order('1'), target_order_id='1', as_of_time=now)
    assert res['decision'] in ['PENDING', 'ESCALATED']
    assert res['proof_certificate']['proof_completeness'] < 1.0
    
def test_wrong_order_evidence_does_not_complete_contract():
    engine = ReconciliationEngine()
    g = ProvenanceGraph()
    dt = now - timedelta(days=2)
    amt = Decimal('100.00')
    o1 = Order(order_id='1', customer_id='C1', amount=amt, status='COMPLETED', created_at=dt)
    p1 = Payment(payment_id='P1', order_id='1', amount=amt, status='CAPTURED', method='card', captured_at=dt)
    
    o2 = Order(order_id='2', customer_id='C2', amount=amt, status='COMPLETED', created_at=dt)
    p2 = Payment(payment_id='P2', order_id='2', amount=amt, status='CAPTURED', method='card', captured_at=dt)
    
    s = Settlement(settlement_id='S1', amount=amt, status='COMPLETED', initiated_at=dt, reference='UTR1')
    si = SettlementItem(item_id='SI1', settlement_id='S1', payment_id='P2', amount=amt) # Only settles P2
    b = BankTransaction(direction='CREDIT', bank_transaction_id='B1', amount=amt, timestamp=dt, reference='UTR1')
    
    g.add_order(o1)
    g.add_payment(p1)
    g.add_order(o2)
    g.add_payment(p2)
    g.add_settlement(s, [si])
    g.add_bank_transaction(b)
    g.link_bank_transaction_to_settlement('B1', 'S1')
    
    res = engine.reconcile_order(g.get_subgraph_for_order('1'), target_order_id='1', as_of_time=now)
    assert res['decision'] in ['PENDING', 'ESCALATED']
    assert res['proof_certificate']['proof_completeness'] < 1.0

def test_n_1_target_vs_context_isolation():
    engine = ReconciliationEngine()
    g = ProvenanceGraph()
    expected_a = Decimal('976.40')
    expected_b = Decimal('1952.80')
    total = expected_a + expected_b
    dt = now - timedelta(days=2)
    
    o_a = Order(order_id='A', customer_id='C1', amount=Decimal('1000.00'), currency='INR', created_at=dt, status='COMPLETED')
    p_a = Payment(payment_id='P_A', order_id='A', amount=Decimal('1000.00'), currency='INR', status='CAPTURED', captured_at=dt, method='card')
    f_a = Fee(fee_id='F_A', payment_id='P_A', type='GATEWAY', amount=Decimal('20.00'), created_at=dt)
    t_a = Tax(tax_id='T_A', payment_id='P_A', type='GST', amount=Decimal('3.60'), created_at=dt)

    o_b = Order(order_id='B', customer_id='C2', amount=Decimal('2000.00'), currency='INR', created_at=dt, status='COMPLETED')
    p_b = Payment(payment_id='P_B', order_id='B', amount=Decimal('2000.00'), currency='INR', status='CAPTURED', captured_at=dt, method='card')

    s = Settlement(settlement_id='S_MULTI', amount=total, currency='INR', status='COMPLETED', initiated_at=dt, reference='UTR_MULTI')
    si_a = SettlementItem(item_id='SI_A', settlement_id='S_MULTI', payment_id='P_A', amount=expected_a)
    si_b = SettlementItem(item_id='SI_B', settlement_id='S_MULTI', payment_id='P_B', amount=Decimal('10.00')) # Corrupted!
    b = BankTransaction(direction='CREDIT', bank_transaction_id='B_MULTI', amount=total, currency='INR', timestamp=dt, reference='UTR_MULTI')

    g.add_order(o_a)
    g.add_payment(p_a)
    g.add_fee(f_a)
    g.add_tax(t_a)
    g.add_order(o_b)
    g.add_payment(p_b)
    g.add_settlement(s, [si_a, si_b])
    g.add_bank_transaction(b)
    g.link_bank_transaction_to_settlement('B_MULTI', 'S_MULTI')

    res = engine.reconcile_order(g.get_subgraph_for_order('A'), target_order_id='A', as_of_time=now)
    assert res['decision'] in ['PENDING', 'ESCALATED']
