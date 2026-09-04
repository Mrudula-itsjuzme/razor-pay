from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch
from models import Order, Payment, Fee, Tax, Settlement, SettlementItem, BankTransaction
from graph import ProvenanceGraph
from reconciliation import ReconciliationEngine

now = datetime(2026, 8, 15, 12, 0, 0)

def test_no_ai_reconciliation_correctness():
    """
    Demonstrates that accounting correctness and reconciliation decisions do NOT depend
    on AI availability. With analyze_exception raising an error, deterministic closure
    gate continues to function perfectly.
    """
    engine = ReconciliationEngine()

    # 1. Clean case -> RECONCILED without AI
    g = ProvenanceGraph()
    dt = now - timedelta(days=2)
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

    with patch('reconciliation.analyze_exception', side_effect=RuntimeError("AI Service Offline")):
        res_clean = engine.reconcile_order(g.get_subgraph_for_order('1'), target_order_id='1', as_of_time=now)
        assert res_clean['decision'] == 'RECONCILED'

    # 2. Insufficient evidence / Missing fee -> ESCALATED safely without AI
    g_exc = ProvenanceGraph()
    o_exc = Order(order_id='2', customer_id='C2', amount=amt, status='COMPLETED', created_at=dt)
    p_exc = Payment(payment_id='P2', order_id='2', amount=amt, status='CAPTURED', method='card', captured_at=dt)
    # Missing bank transaction
    g_exc.add_order(o_exc)
    g_exc.add_payment(p_exc)

    with patch('reconciliation.analyze_exception', side_effect=RuntimeError("AI Service Offline")):
        res_exc = engine.reconcile_order(g_exc.get_subgraph_for_order('2'), target_order_id='2', as_of_time=now)
        assert res_exc['decision'] in ['PENDING', 'ESCALATED']
