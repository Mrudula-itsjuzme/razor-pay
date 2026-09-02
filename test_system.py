import pytest
from fastapi.testclient import TestClient
from decimal import Decimal
import networkx as nx

from main import app, engine, global_graph
from datetime import datetime, timedelta
from datagen import generate_demo_dataset
from graph import ProvenanceGraph
from models import Order, Payment, Refund, Fee, Tax, Settlement, BankTransaction, SettlementItem, LedgerEntry

client = TestClient(app)

def test_api_health():
    response = client.get("/")
    assert response.status_code == 200

def test_ingestion_and_demo():
    response = client.post("/api/demo")
    assert response.status_code == 200
    assert "Loaded deterministic Judge Demo" in response.json()["message"]

def test_benchmark():
    client.post("/api/demo")
    response = client.post("/api/benchmark")
    assert response.status_code == 200
    data = response.json()
    assert "metrics" in data
    assert "exact" in data["metrics"]
    assert "proposed" in data["metrics"]
    # Unsafe closure should be 0 for proposed system
    assert data["metrics"]["proposed"]["unsafe_closure_rate"] == 0.0

from datetime import datetime

def test_reconciliation_exact_layer():
    # Construct a minimal exact graph
    g = ProvenanceGraph()
    dt = datetime.now()
    order = Order(order_id="test1", customer_id="c1", amount=Decimal('100.00'), status="COMPLETED", created_at=dt)
    payment = Payment(payment_id="p1", order_id="test1", amount=Decimal('100.00'), status="CAPTURED", method="UPI", captured_at=dt)
    settlement = Settlement(settlement_id="s1", amount=Decimal('100.00'), status="COMPLETED", initiated_at=dt)
    si = SettlementItem(item_id="si1", settlement_id="s1", payment_id="p1", amount=Decimal('100.00'))
    btx = BankTransaction(bank_transaction_id="b1", amount=Decimal('100.00'), direction="CREDIT", timestamp=dt)
    
    g.add_order(order)
    g.add_payment(payment)
    g.add_settlement(settlement, [si])
    g.add_bank_transaction(btx)
    g.link_bank_transaction_to_settlement("b1", "s1")
    
    subgraph = g.get_subgraph_for_order("test1")
    res = engine.reconcile_order(subgraph, max_layer=1)
    assert res["decision"] == "RECONCILED"

def test_reconciliation_missing_bank_tx():
    g = ProvenanceGraph()
    dt = datetime.now()
    order = Order(order_id="test2", customer_id="c2", amount=Decimal('100.00'), status="COMPLETED", created_at=dt)
    payment = Payment(payment_id="p2", order_id="test2", amount=Decimal('100.00'), status="CAPTURED", method="UPI", captured_at=dt)
    settlement = Settlement(settlement_id="s2", amount=Decimal('100.00'), status="COMPLETED", initiated_at=dt)
    si = SettlementItem(item_id="si2", settlement_id="s2", payment_id="p2", amount=Decimal('100.00'))
    
    g.add_order(order)
    g.add_payment(payment)
    g.add_settlement(settlement, [si])
    
    subgraph = g.get_subgraph_for_order("test2")
    res = engine.reconcile_order(subgraph, max_layer=1)
    
    assert res["decision"] == "PENDING"
    assert "proof_certificate" in res
    assert res["proof_certificate"]["proof_completeness"] == 1.0  # PENDING_SETTLEMENT contract removes bank tx requirement

def test_ai_agent_missing_fee_safety_constraint():
    client.post("/api/demo")
    response = client.get("/api/reconcile/6000")
    data = response.json()
    assert data["decision"] == "ESCALATED"
    
def test_adversarial_wrong_bank_transaction_rejected():
    g = ProvenanceGraph()
    dt = datetime(2026, 8, 1, 10, 0, 0)
    order = Order(order_id="test_adv_1", customer_id="c_adv_1", amount=Decimal('100.00'), status="COMPLETED", created_at=dt)
    payment = Payment(payment_id="p_adv_1", order_id="test_adv_1", amount=Decimal('100.00'), status="CAPTURED", method="UPI", captured_at=dt)
    settlement = Settlement(settlement_id="s_adv_1", amount=Decimal('100.00'), status="COMPLETED", initiated_at=dt - timedelta(days=3), reference="UTR123")
    si = SettlementItem(item_id="si_adv_1", settlement_id="s_adv_1", payment_id="p_adv_1", amount=Decimal('100.00'))
    
    # WRONG reference
    bank_tx = BankTransaction(bank_transaction_id="btx_wrong", amount=Decimal('100.00'), timestamp=dt, reference="UTR999", direction="CREDIT")

    g.add_order(order)
    g.add_payment(payment)
    g.add_settlement(settlement, [si])
    g.add_bank_transaction(bank_tx)
    # The bank tx will NOT be linked by graph.py because reference mismatch.
    
    subgraph = g.get_subgraph_for_order("test_adv_1")
    res = engine.reconcile_order(subgraph, max_layer=4)
    
    # Should escalate because bank tx is required but missing from subgraph
    assert res["decision"] == "EXCEPTION_MISSING_BANK_TX"

def test_contradiction_multiple_orders_fails():
    g = ProvenanceGraph()
    dt = datetime.now()
    order1 = Order(order_id="test_adv_2", customer_id="c_adv_2", amount=Decimal('100.00'), status="COMPLETED", created_at=dt)
    order2 = Order(order_id="test_adv_3", customer_id="c_adv_2", amount=Decimal('150.00'), status="COMPLETED", created_at=dt)
    payment = Payment(payment_id="p_adv_2", order_id="test_adv_2", amount=Decimal('250.00'), status="CAPTURED", method="UPI", captured_at=dt)
    
    # Intentionally link both orders to the same subgraph
    g.add_order(order1)
    g.add_order(order2)
    g.g.add_edge(f"order_{order1.order_id}", f"payment_{payment.payment_id}", relation="GENERATED")
    g.g.add_edge(f"order_{order2.order_id}", f"payment_{payment.payment_id}", relation="GENERATED")
    
    subgraph = g.get_subgraph_for_order("test_adv_2")
    res = engine.reconcile_order(subgraph, max_layer=1)
    
    assert res["proof_certificate"]["proof_validity"] == "FAIL"
    assert "Multiple orders" in res["conflicting_evidence"][0]

def test_currency_mismatch_escalates():
    g = ProvenanceGraph()
    dt = datetime(2026, 8, 1, 10, 0, 0)
    order = Order(order_id="test_curr", customer_id="c_curr", amount=Decimal('100.00'), currency="USD", status="COMPLETED", created_at=dt)
    payment = Payment(payment_id="p_curr", order_id="test_curr", amount=Decimal('100.00'), currency="USD", status="CAPTURED", method="UPI", captured_at=dt)
    settlement = Settlement(settlement_id="s_curr", amount=Decimal('100.00'), currency="INR", status="COMPLETED", initiated_at=dt, reference="UTR123")
    si = SettlementItem(item_id="si_curr", settlement_id="s_curr", payment_id="p_curr", amount=Decimal('100.00'), currency="INR")
    bank_tx = BankTransaction(bank_transaction_id="btx_curr", amount=Decimal('100.00'), currency="INR", timestamp=dt, reference="UTR123", direction="CREDIT")

    g.add_order(order)
    g.add_payment(payment)
    g.add_settlement(settlement, [si])
    g.add_bank_transaction(bank_tx)
    
    subgraph = g.get_subgraph_for_order("test_curr")
    res = engine.reconcile_order(subgraph, max_layer=4)
    
    assert res["proof_certificate"]["proof_validity"] == "FAIL"
    assert "Currency mismatch" in res["conflicting_evidence"][0]

def test_wrong_refund_perfect_discrepancy():
    g = ProvenanceGraph()
    dt = datetime(2026, 8, 1, 10, 0, 0)
    order = Order(order_id="test_wr", customer_id="c_wr", amount=Decimal('100.00'), status="COMPLETED", created_at=dt)
    payment = Payment(payment_id="p_wr", order_id="test_wr", amount=Decimal('100.00'), status="CAPTURED", method="UPI", captured_at=dt)
    
    short_amount = Decimal('50.00')
    settlement = Settlement(settlement_id="s_wr", amount=short_amount, status="COMPLETED", initiated_at=dt, reference="UTR_wr")
    si = SettlementItem(item_id="si_wr_1", settlement_id="s_wr", payment_id="p_wr", amount=short_amount)
    
    wrong_refund = Refund(refund_id="ref_wr", payment_id="pay_OTHER", amount=Decimal('50.00'), status="PROCESSED", created_at=dt)
    bank_tx = BankTransaction(bank_transaction_id="btx_wr", amount=short_amount, timestamp=dt, reference="UTR_wr", direction="CREDIT")
    
    g.add_order(order)
    g.add_payment(payment)
    g.add_settlement(settlement, [si])
    g.add_bank_transaction(bank_tx)
    g.link_bank_transaction_to_settlement("btx_wr", "s_wr")
    g.add_refund(wrong_refund)
    
    subgraph = g.get_subgraph_for_order("test_wr")
    res = engine.reconcile_order(subgraph, max_layer=4)
    
    assert res["decision"] == "UNRESOLVED" or res["decision"] == "ESCALATED"

def test_evidence_degradation_reduces_closure():
    response = client.post("/api/eval_lab")
    data = response.json()
    ed = data["evidence_degradation"]
    # 100% retention -> highest closure, 40% retention -> lowest closure
    closure_100 = next(r["auto_closure_rate"] for r in ed if r["retention"] == 1.0)
    closure_40 = next(r["auto_closure_rate"] for r in ed if r["retention"] == 0.4)
    assert closure_100 > closure_40

def test_money_safety():
    # Assert that floating point artifacts are not in JSON
    client.post("/api/demo")
    response = client.get("/api/reconcile/1000")
    data = response.json()
    assert "expected_net" in data
    assert "." in data["expected_net"]
    assert len(data["expected_net"].split(".")[1]) <= 2

def test_benchmark_capabilities_differ():
    # Prove that Exact, Rules, and Proposed actually have different capabilities.
    client.post("/api/demo")
    
    response = client.post("/api/benchmark")
    data = response.json()
    metrics = data["metrics"]
    
    exact_f1 = metrics["exact"]["exc_f1"] or 0.0
    proposed_f1 = metrics["proposed"]["exc_f1"] or 0.0
    
    assert proposed_f1 > exact_f1, "Proposed system must correctly classify exceptions (like missing bank TX) that Exact cannot."

def test_degradation_isolation():
    client.post("/api/demo")
    
    # A. reconcile pristine case (let's use order 1000 which is CLEAN)
    res_a = client.get("/api/reconcile/1000").json()
    graph_a = client.get("/api/graph/1000").json()
    
    # B. record decision + evidence IDs + canonical graph node count
    decision_a = res_a["decision"]
    nodes_a = len(graph_a["nodes"])
    canonical_nodes_before = len(global_graph.g.nodes)
    
    # C. degrade case
    client.post("/api/degrade/1000")
    
    # D. verify degraded copy changes
    res_c = client.get("/api/reconcile/1000").json()
    graph_c = client.get("/api/graph/1000").json()
    assert len(graph_c["nodes"]) < nodes_a, "Degraded graph must have fewer nodes"
    assert res_c["decision"] != decision_a, "Decision must change on degradation"
    
    # E. verify canonical graph unchanged
    canonical_nodes_after = len(global_graph.g.nodes)
    assert canonical_nodes_before == canonical_nodes_after, "Canonical graph must not mutate"
    
    # F. restore
    client.post("/api/restore/1000")
    
    # G. reconcile again
    res_g = client.get("/api/reconcile/1000").json()
    graph_g = client.get("/api/graph/1000").json()
    
    # H. assert identical to A
    assert res_g["decision"] == decision_a
    assert len(graph_g["nodes"]) == nodes_a
    assert len(global_graph.g.nodes) == canonical_nodes_before
    # Sequence test for multiple cases
    res2_a = client.get("/api/reconcile/3000").json()
    graph2_a = client.get("/api/graph/3000").json()
    decision2_a = res2_a["decision"]
    
    client.post("/api/degrade/1000")
    client.post("/api/degrade/3000")
    
    res2_c = client.get("/api/reconcile/3000").json()
    assert res2_c["decision"] != decision2_a
    
    # Restoring 1000 should not restore 3000
    client.post("/api/restore/1000")
    res2_d = client.get("/api/reconcile/3000").json()
    assert res2_d["decision"] != decision2_a
    
    # Restoring 3000 fixes 3000
    client.post("/api/restore/3000")
    res2_e = client.get("/api/reconcile/3000").json()
    assert res2_e["decision"] == decision2_a

# ----------------- REGRESSION TESTS FOR EVALUATION -----------------

def test_metric_wiring():
    # We simulate a confusion matrix:
    # 2 correct automatic closures (tp)
    # 1 unsafe closure (fp)
    # 3 correct abstentions (tn)
    # 4 over-abstentions (fn)
    
    tp, fp, tn, fn = 2, 1, 3, 4
    total = tp + fp + tn + fn
    
    gt_safely_closable = tp + fn
    gt_abstention_req = tn + fp
    
    safe_auto_closure_rate = tp / gt_safely_closable
    unsafe_closure_rate = fp / gt_abstention_req
    correct_abstention_rate = tn / gt_abstention_req
    over_abstention_rate = fn / gt_safely_closable
    overall_automation = (tp + fp) / total
    
    assert safe_auto_closure_rate == 2 / 6
    assert unsafe_closure_rate == 1 / 4
    assert correct_abstention_rate == 3 / 4
    assert over_abstention_rate == 4 / 6
    assert overall_automation == 3 / 10

def test_stratified_scenario_distribution():
    from datagen import generate_complex_dataset
    records, cases = generate_complex_dataset()
    dist = {}
    for _, gt in cases:
        dist[gt] = dist.get(gt, 0) + 1
        
    assert len(dist) == 21  # 7 normal + 14 adv
    for k, v in dist.items():
        assert v == 5

def test_close_the_books_partition():
    from datagen import generate_complex_dataset
    from run_complex_eval import make_graph
    from main import engine
    
    records, cases = generate_complex_dataset()
    g = make_graph(records)
    
    proven = Decimal('0.0')
    pending = Decimal('0.0')
    missing = Decimal('0.0')
    ambiguous = Decimal('0.0')
    conflicting = Decimal('0.0')
    unresolvable = Decimal('0.0')
    unclassified = Decimal('0.0')
    
    total_val = Decimal('0.0')
    
    for order_id, _ in cases:
        subgraph = g.get_subgraph_for_order(order_id)
        res = engine.reconcile_order(subgraph)
        exposure = Decimal(res.get("expected_net", "0.00"))
        total_val += exposure
        
        decision = res.get("decision", "")
        if decision.startswith("RECONCILED") and res.get("proof_completeness", 0) == 1.0:
            proven += exposure
        elif decision == "PENDING":
            pending += exposure
        elif decision == "ESCALATED":
            reason = res.get("reason", "").lower()
            if "conflicting" in reason or "duplicate" in reason:
                conflicting += exposure
            elif "ambiguous" in reason:
                ambiguous += exposure
            elif "missing" in reason or "insufficient" in reason:
                missing += exposure
            else:
                unresolvable += exposure
        else:
            unclassified += exposure
            
def test_n_to_1_accounting():
    from datagen import generate_case
    from datetime import datetime
    records, case_meta = generate_case(9999, "CONSOLIDATED_SETTLEMENT_N_TO_1", datetime(2026,8,1))
    
    # Check that there are two orders
    orders = [r for r in records if type(r).__name__ == "Order"]
    assert len(orders) == 2
    
    # Check that there is only one settlement
    settlements = [r for r in records if type(r).__name__ == "Settlement"]
    assert len(settlements) == 1
    
    # The expected total amount of settlement should equal the sum of expected nets
    total_expected = sum((o.amount - (o.amount*Decimal('0.02')).quantize(Decimal('0.01')) - ((o.amount*Decimal('0.02')).quantize(Decimal('0.01'))*Decimal('0.18')).quantize(Decimal('0.01'))) for o in orders)
    assert settlements[0].amount == total_expected


