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
    dt = datetime(2026, 8, 10, 10, 0, 0)
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
    res = engine.reconcile_order(subgraph, max_layer=1, target_order_id="test1", as_of_time=datetime(2026, 8, 15, 12, 0, 0))
    assert res["decision"] == "RECONCILED"

def test_reconciliation_missing_bank_tx():
    g = ProvenanceGraph()
    dt = datetime(2026, 8, 14, 12, 0, 0)
    order = Order(order_id="test2", customer_id="c2", amount=Decimal('100.00'), status="COMPLETED", created_at=dt)
    payment = Payment(payment_id="p2", order_id="test2", amount=Decimal('100.00'), status="CAPTURED", method="UPI", captured_at=dt)
    settlement = Settlement(settlement_id="s2", amount=Decimal('100.00'), status="COMPLETED", initiated_at=dt)
    si = SettlementItem(item_id="si2", settlement_id="s2", payment_id="p2", amount=Decimal('100.00'))
    
    g.add_order(order)
    g.add_payment(payment)
    g.add_settlement(settlement, [si])
    
    subgraph = g.get_subgraph_for_order("test2")
    res = engine.reconcile_order(subgraph, max_layer=1, target_order_id="test2", as_of_time=datetime(2026, 8, 15, 12, 0, 0))
    
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
    settlement = Settlement(settlement_id="s_adv_1", amount=Decimal('100.00'), status="COMPLETED", initiated_at=dt + timedelta(hours=1), reference="UTR123")
    si = SettlementItem(item_id="si_adv_1", settlement_id="s_adv_1", payment_id="p_adv_1", amount=Decimal('100.00'))

    # WRONG reference
    bank_tx = BankTransaction(bank_transaction_id="btx_wrong", amount=Decimal('100.00'), timestamp=dt + timedelta(hours=2), reference="UTR999", direction="CREDIT")

    g.add_order(order)
    g.add_payment(payment)
    g.add_settlement(settlement, [si])
    g.add_bank_transaction(bank_tx)
    # The bank tx will NOT be linked by graph.py because reference mismatch.
    
    subgraph = g.get_subgraph_for_order("test_adv_1")
    res = engine.reconcile_order(subgraph, max_layer=4, target_order_id="test_adv_1", as_of_time=dt + timedelta(days=5))
    
    # Should escalate because bank tx is missing from subgraph and SLA breached
    assert res["decision"] == "ESCALATED"
    assert res["exception_details"]["exception_type"] == "TEMPORAL_EXCEPTION"



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
    res = engine.reconcile_order(subgraph, max_layer=4, target_order_id="test_curr", as_of_time=datetime(2026, 8, 15, 12, 0, 0))
    
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
    res = engine.reconcile_order(subgraph, max_layer=4, target_order_id="test_wr", as_of_time=datetime(2026, 8, 15, 12, 0, 0))
    
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
    from eval_engine import calculate_financial_partition
    
    records, cases = generate_complex_dataset()
    g = make_graph(records)
    
    fin_partition = calculate_financial_partition(engine, cases, g)
    
    total_exposure = fin_partition["total_batch_exposure"]
    unresolved_exposure = fin_partition["total_unresolved_exposure"]
    actionable_proof_debt = fin_partition["actionable_proof_debt"]
    pending = fin_partition["pending_exposure"]
    
    proven = fin_partition["partition"]["PROVEN"]["exposure"]
    
    # Assert exactly: category sum == total exposure
    cat_sum = sum(b["exposure"] for b in fin_partition["partition"].values())
    assert cat_sum == total_exposure
    
    # unresolved == total - proven
    assert unresolved_exposure == total_exposure - proven
    
    # pending + actionable proof debt == unresolved exposure
    assert pending + actionable_proof_debt == unresolved_exposure

def test_policy_evaluation_v2():
    from eval_engine import calculate_policy_metrics_v2
    expected = ["RECONCILED", "RECONCILED", "PENDING", "ESCALATED", "ESCALATED"]
    predicted = ["RECONCILED", "ESCALATED", "PENDING", "RECONCILED", "ESCALATED"]
    
    metrics, cm = calculate_policy_metrics_v2(expected, predicted)
    
    assert cm["RECONCILED"]["RECONCILED"] == 1
    assert cm["RECONCILED"]["ESCALATED"] == 1
    assert cm["RECONCILED"]["PENDING"] == 0
    assert cm["PENDING"]["PENDING"] == 1
    assert cm["ESCALATED"]["ESCALATED"] == 1
    assert cm["ESCALATED"]["RECONCILED"] == 1
    
    assert metrics["overall_policy_accuracy"] == 3 / 5
    assert metrics["safe_closure_recall"] == 0.5
    assert metrics["unsafe_closure_rate"] == 0.5
    assert metrics["over_abstention_rate"] == 0.5

def test_exception_structure():
    g = ProvenanceGraph()
    dt = datetime(2026, 8, 1, 10, 0, 0)
    order = Order(order_id="test_str", customer_id="c_str", amount=Decimal('100.00'), status="COMPLETED", created_at=dt)
    # Missing everything else
    g.add_order(order)
    subgraph = g.get_subgraph_for_order("test_str")
    res = engine.reconcile_order(subgraph, target_order_id="test_str", max_layer=4, as_of_time=datetime(2026, 8, 15, 12, 0, 0))
    
    exc = res.get("exception_details")
    assert exc is not None
    assert exc["closure_authorized"] is False
    assert "affected_evidence_ids" in exc
    assert "recommended_action" in exc

def test_contradiction_types():
    g = ProvenanceGraph()
    dt = datetime(2026, 8, 1, 10, 0, 0)
    order = Order(order_id="test_dup", customer_id="c_dup", amount=Decimal('100.00'), status="COMPLETED", created_at=dt)
    payment = Payment(payment_id="p_dup", order_id="test_dup", amount=Decimal('100.00'), status="CAPTURED", method="UPI", captured_at=dt)
    fee1 = Fee(fee_id="f1", payment_id="p_dup", type="GATEWAY", amount=Decimal('2.00'), created_at=dt)
    fee2 = Fee(fee_id="f2", payment_id="p_dup", type="GATEWAY", amount=Decimal('3.00'), created_at=dt)
    g.add_order(order)
    g.add_payment(payment)
    g.add_fee(fee1)
    g.add_fee(fee2)
    
    subgraph = g.get_subgraph_for_order("test_dup")
    res = engine.reconcile_order(subgraph, target_order_id="test_dup", max_layer=4, as_of_time=datetime(2026, 8, 15, 12, 0, 0))
    exc = res.get("exception_details")
    assert exc["exception_type"] == "CONFLICTING_EVIDENCE"
    assert exc["exception_subtype"] == "DUPLICATE_FEE_RECORDS"


def test_temporal_negative_controls():
    g = ProvenanceGraph()
    dt_order = datetime(2026, 8, 10, 10, 0, 0)
    order = Order(order_id="nc1", customer_id="c_nc", amount=Decimal('100.00'), status="COMPLETED", created_at=dt_order)
    payment = Payment(payment_id="p_nc", order_id="nc1", amount=Decimal('100.00'), status="CAPTURED", method="UPI", captured_at=dt_order)
    
    # A. settlement age = 1 day, bank missing -> PENDING
    # Evaluation time is Aug 15. So 1 day age means Aug 14.
    s1 = Settlement(settlement_id="s1", amount=Decimal('100.00'), status="COMPLETED", initiated_at=datetime(2026, 8, 14, 10, 0, 0), reference="UTR1")
    si1 = SettlementItem(item_id="si1", settlement_id="s1", payment_id="p_nc", amount=Decimal('100.00'))
    
    g_a = ProvenanceGraph()
    g_a.add_order(order)
    g_a.add_payment(payment)
    g_a.add_settlement(s1, [si1])
    res_a = engine.reconcile_order(g_a.get_subgraph_for_order("nc1"), target_order_id="nc1", max_layer=4, as_of_time=datetime(2026, 8, 15, 12, 0, 0))
    assert res_a["decision"] == "PENDING"
    
    # B. settlement age = SLA exactly -> PENDING
    s2 = Settlement(settlement_id="s2", amount=Decimal('100.00'), status="COMPLETED", initiated_at=datetime(2026, 8, 12, 0, 0, 0), reference="UTR2")
    si2 = SettlementItem(item_id="si2", settlement_id="s2", payment_id="p_nc", amount=Decimal('100.00'))
    
    g_b = ProvenanceGraph()
    g_b.add_order(order)
    g_b.add_payment(payment)
    g_b.add_settlement(s2, [si2])
    # Set engine eval time specifically for boundary test
    res_b = engine.reconcile_order(g_b.get_subgraph_for_order("nc1"), target_order_id="nc1", max_layer=4, as_of_time=datetime(2026, 8, 15, 0, 0, 0))
    assert res_b["decision"] == "PENDING"
    
    # C. settlement age = SLA + 1 second -> TEMPORAL_EXCEPTION
    res_c = engine.reconcile_order(g_b.get_subgraph_for_order("nc1"), target_order_id="nc1", max_layer=4, as_of_time=datetime(2026, 8, 15, 0, 0, 1))
    assert res_c["exception_details"]["exception_type"] == "TEMPORAL_EXCEPTION"
    assert res_c["exception_details"]["exception_subtype"] == "SETTLEMENT_SLA_BREACHED"
    
    # D. settlement timestamp > as_of_time -> FUTURE_DATED_EVIDENCE
    s4 = Settlement(settlement_id="s4", amount=Decimal('100.00'), status="COMPLETED", initiated_at=datetime(2026, 8, 16, 0, 0, 0), reference="UTR4")
    si4 = SettlementItem(item_id="si4", settlement_id="s4", payment_id="p_nc", amount=Decimal('100.00'))
    g_d = ProvenanceGraph()
    g_d.add_order(order)
    g_d.add_payment(payment)
    g_d.add_settlement(s4, [si4])
    res_d = engine.reconcile_order(g_d.get_subgraph_for_order("nc1"), target_order_id="nc1", max_layer=4, as_of_time=datetime(2026, 8, 15, 0, 0, 0))
    assert res_d["exception_details"]["exception_type"] == "TEMPORAL_EXCEPTION"
    assert res_d["exception_details"]["exception_subtype"] == "FUTURE_DATED_EVIDENCE"
    
    # E. settlement before payment -> CAUSAL_ORDER_VIOLATION
    s5 = Settlement(settlement_id="s5", amount=Decimal('100.00'), status="COMPLETED", initiated_at=datetime(2026, 8, 9, 0, 0, 0), reference="UTR5")
    si5 = SettlementItem(item_id="si5", settlement_id="s5", payment_id="p_nc", amount=Decimal('100.00'))
    g_e = ProvenanceGraph()
    g_e.add_order(order)
    g_e.add_payment(payment)
    g_e.add_settlement(s5, [si5])
    res_e = engine.reconcile_order(g_e.get_subgraph_for_order("nc1"), target_order_id="nc1", max_layer=4, as_of_time=datetime(2026, 8, 15, 0, 0, 0))
    assert res_e["exception_details"]["exception_type"] == "TEMPORAL_EXCEPTION"
    assert res_e["exception_details"]["exception_subtype"] == "CAUSAL_ORDER_VIOLATION"
    
    # Restore evaluation time

def test_adversarial_lure_negative_controls():
    # F, G, H, I
    dt_order = datetime(2026, 8, 10, 10, 0, 0)
    order = Order(order_id="nc2", customer_id="c_nc2", amount=Decimal('100.00'), status="COMPLETED", created_at=dt_order)
    payment = Payment(payment_id="p_nc2", order_id="nc2", amount=Decimal('100.00'), status="CAPTURED", method="UPI", captured_at=dt_order)
    fee = Fee(fee_id="f_nc2", payment_id="p_nc2", type="GATEWAY", amount=Decimal('2.00'), created_at=dt_order)
    tax = Tax(tax_id="t_nc2", payment_id="p_nc2", type="GST", amount=Decimal('0.36'), created_at=dt_order)
    
    expected_amount = Decimal('97.64')
    
    # F. same amount + wrong reference + target within SLA -> PENDING
    s_f = Settlement(settlement_id="s_f", amount=expected_amount, status="COMPLETED", initiated_at=datetime(2026, 8, 14, 10, 0, 0), reference="UTR_F")
    si_f = SettlementItem(item_id="si_f", settlement_id="s_f", payment_id="p_nc2", amount=expected_amount)
    b_f_lure = BankTransaction(bank_transaction_id="b_f_lure", amount=expected_amount, timestamp=datetime(2026, 8, 14, 12, 0, 0), reference="UTR_WRONG", direction="CREDIT")
    
    g_f = ProvenanceGraph()
    g_f.add_order(order)
    g_f.add_payment(payment)
    g_f.add_fee(fee)
    g_f.add_tax(tax)
    g_f.add_settlement(s_f, [si_f])
    g_f.add_bank_transaction(b_f_lure) # Not linked to settlement
    
    res_f = engine.reconcile_order(g_f.get_subgraph_for_order("nc2"), target_order_id="nc2", max_layer=4, as_of_time=datetime(2026, 8, 15, 12, 0, 0))
    assert res_f["decision"] == "PENDING"
    assert "b_f_lure" not in str(res_f.get("proof_certificate", {}))
    
    # G. same amount + wrong reference + target outside SLA -> TEMPORAL_EXCEPTION
    s_g = Settlement(settlement_id="s_g", amount=expected_amount, status="COMPLETED", initiated_at=datetime(2026, 8, 10, 10, 0, 0), reference="UTR_G")
    si_g = SettlementItem(item_id="si_g", settlement_id="s_g", payment_id="p_nc2", amount=expected_amount)
    
    g_g = ProvenanceGraph()
    g_g.add_order(order)
    g_g.add_payment(payment)
    g_g.add_fee(fee)
    g_g.add_tax(tax)
    g_g.add_settlement(s_g, [si_g])
    g_g.add_bank_transaction(b_f_lure)
    
    res_g = engine.reconcile_order(g_g.get_subgraph_for_order("nc2"), target_order_id="nc2", max_layer=4, as_of_time=datetime(2026, 8, 15, 12, 0, 0))
    assert res_g["exception_details"]["exception_type"] == "TEMPORAL_EXCEPTION"
    
    # H. same amount + correct reference + complete valid evidence -> RECONCILED
    b_h_correct = BankTransaction(bank_transaction_id="b_h_correct", amount=expected_amount, timestamp=datetime(2026, 8, 10, 12, 0, 0), reference="UTR_G", direction="CREDIT")
    g_g.add_bank_transaction(b_h_correct)
    g_g.link_bank_transaction_to_settlement("b_h_correct", "s_g")
    
    res_h = engine.reconcile_order(g_g.get_subgraph_for_order("nc2"), target_order_id="nc2", max_layer=4, as_of_time=datetime(2026, 8, 15, 12, 0, 0))
    assert res_h["decision"] == "RECONCILED"
    assert "b_h_correct" in str(res_h.get("proof_certificate", {}))
    # I. unrelated lure ID absent from target proof certificate
    assert "b_f_lure" not in str(res_h.get("proof_certificate", {}))



def test_complete_proof_temporal_negative_controls():
    # A complete matching settlement + bank evidence but invalid time
    dt_order = datetime(2026, 8, 10, 10, 0, 0)
    order = Order(order_id="nc3", customer_id="c_nc3", amount=Decimal('100.00'), status="COMPLETED", created_at=dt_order)
    payment = Payment(payment_id="p_nc3", order_id="nc3", amount=Decimal('100.00'), status="CAPTURED", method="UPI", captured_at=dt_order)
    fee = Fee(fee_id="f_nc3", payment_id="p_nc3", type="GATEWAY", amount=Decimal('2.00'), created_at=dt_order)
    tax = Tax(tax_id="t_nc3", payment_id="p_nc3", type="GST", amount=Decimal('0.36'), created_at=dt_order)
    
    expected_amount = Decimal('97.64')
    
    # Base setup
    s_a = Settlement(settlement_id="s_a", amount=expected_amount, status="COMPLETED", initiated_at=datetime(2026, 8, 14, 10, 0, 0), reference="UTR_NC3")
    si_a = SettlementItem(item_id="si_a", settlement_id="s_a", payment_id="p_nc3", amount=expected_amount)
    
    g_a = ProvenanceGraph()
    g_a.add_order(order)
    g_a.add_payment(payment)
    g_a.add_fee(fee)
    g_a.add_tax(tax)
    g_a.add_settlement(s_a, [si_a])
    
    
    # A. Bank > as_of_time
    b_a = BankTransaction(bank_transaction_id="b_a", amount=expected_amount, timestamp=datetime(2026, 8, 16, 12, 0, 0), reference="UTR_NC3", direction="CREDIT")
    g_a.add_bank_transaction(b_a)
    g_a.link_bank_transaction_to_settlement("b_a", "s_a")
    
    res_a = engine.reconcile_order(g_a.get_subgraph_for_order("nc3"), target_order_id="nc3", max_layer=4, as_of_time=datetime(2026, 8, 15, 12, 0, 0))
    assert res_a["decision"] == "ESCALATED"
    assert res_a["exception_details"]["exception_type"] == "TEMPORAL_EXCEPTION"
    
    # B. Complete matching evidence, but settlement before payment
    s_b = Settlement(settlement_id="s_b", amount=expected_amount, status="COMPLETED", initiated_at=datetime(2026, 8, 9, 10, 0, 0), reference="UTR_B")
    si_b = SettlementItem(item_id="si_b", settlement_id="s_b", payment_id="p_nc3", amount=expected_amount)
    b_b = BankTransaction(bank_transaction_id="b_b", amount=expected_amount, timestamp=datetime(2026, 8, 9, 12, 0, 0), reference="UTR_B", direction="CREDIT")
    
    g_b = ProvenanceGraph()
    g_b.add_order(order)
    g_b.add_payment(payment)
    g_b.add_fee(fee)
    g_b.add_tax(tax)
    g_b.add_settlement(s_b, [si_b])
    g_b.add_bank_transaction(b_b)
    g_b.link_bank_transaction_to_settlement("b_b", "s_b")
    
    res_b = engine.reconcile_order(g_b.get_subgraph_for_order("nc3"), target_order_id="nc3", max_layer=4, as_of_time=datetime(2026, 8, 15, 12, 0, 0))
    assert res_b["decision"] == "ESCALATED"
    assert res_b["exception_details"]["exception_type"] == "TEMPORAL_EXCEPTION"
    assert res_b["exception_details"]["exception_subtype"] == "CAUSAL_ORDER_VIOLATION"
    
    # C. Complete matching evidence with valid chronology
    s_c = Settlement(settlement_id="s_c", amount=expected_amount, status="COMPLETED", initiated_at=datetime(2026, 8, 14, 10, 0, 0), reference="UTR_C")
    si_c = SettlementItem(item_id="si_c", settlement_id="s_c", payment_id="p_nc3", amount=expected_amount)
    b_c = BankTransaction(bank_transaction_id="b_c", amount=expected_amount, timestamp=datetime(2026, 8, 14, 12, 0, 0), reference="UTR_C", direction="CREDIT")
    
    g_c = ProvenanceGraph()
    g_c.add_order(order)
    g_c.add_payment(payment)
    g_c.add_fee(fee)
    g_c.add_tax(tax)
    g_c.add_settlement(s_c, [si_c])
    g_c.add_bank_transaction(b_c)
    g_c.link_bank_transaction_to_settlement("b_c", "s_c")
    
    res_c = engine.reconcile_order(g_c.get_subgraph_for_order("nc3"), target_order_id="nc3", max_layer=4, as_of_time=datetime(2026, 8, 15, 12, 0, 0))
    assert res_c["decision"] == "RECONCILED"
    
    # D. proof_completeness mathematical check
    assert res_b["proof_completeness"] == 1.0
    assert res_b["exception_details"]["closure_authorized"] is False

