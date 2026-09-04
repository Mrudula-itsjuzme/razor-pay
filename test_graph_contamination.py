from datetime import datetime
from decimal import Decimal
from graph import ProvenanceGraph
from models import Order, Payment, Settlement, SettlementItem

def test_subgraph_extraction():
    g = ProvenanceGraph()
    now = datetime.now()

    # Customer 1
    o1 = Order(order_id="1", customer_id="C1", amount=Decimal('100.00'), currency="INR", status="COMPLETED", created_at=now)
    p1 = Payment(payment_id="P1", order_id="1", amount=Decimal('100.00'), currency="INR", status="CAPTURED", captured_at=now, method="card")

    # Customer 1 second order
    o2 = Order(order_id="2", customer_id="C1", amount=Decimal('50.00'), currency="INR", status="COMPLETED", created_at=now)
    p2 = Payment(payment_id="P2", order_id="2", amount=Decimal('50.00'), currency="INR", status="CAPTURED", captured_at=now, method="card")

    g.add_order(o1)
    g.add_payment(p1)
    g.add_order(o2)
    g.add_payment(p2)

    s = Settlement(settlement_id="S1", amount=Decimal('150.00'), currency="INR", status="COMPLETED", reference="UTR1", initiated_at=now)
    si1 = SettlementItem(item_id="SI1", settlement_id="S1", payment_id="P1", refund_id=None, amount=Decimal('100.00'))
    si2 = SettlementItem(item_id="SI2", settlement_id="S1", payment_id="P2", refund_id=None, amount=Decimal('50.00'))
    g.add_settlement(s, [si1, si2])

    subgraph = g.get_subgraph_for_order("1")

    # Should contain Order 1, Payment 1, Settlement S1, Customer C1
    # Should NOT contain Order 2, Payment 2

    target_nodes = [n for n, d in subgraph.nodes(data=True) if d.get('is_target_evidence')]
    context_nodes = [n for n, d in subgraph.nodes(data=True) if not d.get('is_target_evidence')]

    assert "order_1" in target_nodes
    assert "payment_P1" in target_nodes
    assert "settlement_S1" in target_nodes
    assert "customer_C1" in target_nodes
    assert "order_2" not in target_nodes

    # payment_P2 is pulled in as settlement context but NOT as target evidence
    assert "payment_P2" not in target_nodes
    assert "payment_P2" in context_nodes
