import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from graph import ProvenanceGraph
from models import Order, Payment, Settlement, SettlementItem, BankTransaction
from reconciliation import ReconciliationEngine
from unittest.mock import patch

now = datetime(2026, 8, 15, 12, 0, 0)
engine = ReconciliationEngine()

def test_ai_malicious_reconciled():
    g = ProvenanceGraph()
    # Create invalid case: No fee/tax but missing amount
    g.add_order(Order(order_id="1", customer_id="C1", amount=Decimal('100.00'), currency="INR", created_at=now - timedelta(days=2), status="COMPLETED"))
    g.add_payment(Payment(payment_id="P1", order_id="1", amount=Decimal('100.00'), currency="INR", status="CAPTURED", captured_at=now - timedelta(days=2, hours=-1), method="card"))
    g.add_settlement(Settlement(settlement_id="S1", amount=Decimal('90.00'), currency="INR", status="COMPLETED", initiated_at=now - timedelta(days=1), reference="UTR1"), [SettlementItem(item_id="SI1", settlement_id="S1", payment_id="P1", refund_id=None, amount=Decimal('90.00'))])
    b = BankTransaction(direction="CREDIT", bank_transaction_id="B1", amount=Decimal('90.00'), currency="INR", timestamp=now, reference="UTR1")
    g.add_bank_transaction(b)
    g.link_bank_transaction_to_settlement("B1", "S1")
    
    subgraph = g.get_subgraph_for_order("1")
    
    # Mock AI to return a RECONCILED decision with high confidence
    with patch("reconciliation.analyze_exception") as mock_analyze:
        mock_analyze.return_value = {
            "recommended_action": "RECONCILED_FIXED_ACCOUNTING",
            "confidence": "1.0",
            "likely_causes": ["AI forced reconciliation"]
        }
        
        res = engine.reconcile_order(subgraph, target_order_id="1", as_of_time=now, max_layer=4)
        
        # System must NOT accept the AI's closure authority
        assert not res['decision'].startswith("RECONCILED")
        assert res['decision'] == "ESCALATED"
        assert res['decision_authority'] == "HUMAN_REVIEW_REQUIRED"
        assert res['proof_gap_report'] is not None

def test_ai_unavailable():
    g = ProvenanceGraph()
    # Create valid case
    g.add_order(Order(order_id="2", customer_id="C1", amount=Decimal('100.00'), currency="INR", created_at=now - timedelta(days=2), status="COMPLETED"))
    g.add_payment(Payment(payment_id="P2", order_id="2", amount=Decimal('100.00'), currency="INR", status="CAPTURED", captured_at=now - timedelta(days=2, hours=-1), method="card"))
    g.add_settlement(Settlement(settlement_id="S2", amount=Decimal('100.00'), currency="INR", status="COMPLETED", initiated_at=now - timedelta(days=1), reference="UTR2"), [SettlementItem(item_id="SI2", settlement_id="S2", payment_id="P2", refund_id=None, amount=Decimal('100.00'))])
    b = BankTransaction(direction="CREDIT", bank_transaction_id="B2", amount=Decimal('100.00'), currency="INR", timestamp=now, reference="UTR2")
    g.add_bank_transaction(b)
    g.link_bank_transaction_to_settlement("B2", "S2")
    
    subgraph = g.get_subgraph_for_order("2")
    
    # Valid case must reconcile perfectly without AI
    with patch("reconciliation.analyze_exception", side_effect=RuntimeError("AI unavailable")):
        res = engine.reconcile_order(subgraph, target_order_id="2", as_of_time=now, max_layer=4)
        
        assert res['decision'] == "RECONCILED"
        assert res['decision_authority'] == "DETERMINISTIC"
