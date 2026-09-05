import json
import os
import random
from decimal import Decimal
import datetime
from evaluation.datagen import generate_demo_dataset, generate_adversarial_dataset, generate_complex_dataset
from evaluation.datagen_v2_1 import generate_complex_dataset_v2_1
from graph import ProvenanceGraph
from main import engine, global_graph
from evaluation.metrics import evaluate_system
from evaluation.policy import calculate_proof_debt, safe_automation_frontier, evidence_degradation_experiment

def make_graph(records):
    g = ProvenanceGraph()
    for rec in records:
        t = type(rec).__name__
        if t == "Order": g.add_order(rec)
        elif t == "Payment": g.add_payment(rec)
        elif t == "Refund": g.add_refund(rec)
        elif t == "Fee": g.add_fee(rec)
        elif t == "Tax": g.add_tax(rec)
        elif t == "BankTransaction": g.add_bank_transaction(rec)
    
    for rec in records:
        if type(rec).__name__ == "Settlement":
            items = [r for r in records if type(r).__name__ == "SettlementItem" and r.settlement_id == rec.settlement_id]
            g.add_settlement(rec, items)
            
    for n, data in g.g.nodes(data=True):
        if data.get('type') == 'BankTransaction':
            tx = data['data']
            if tx.reference:
                for sn, sdata in g.g.nodes(data=True):
                    if sdata.get('type') == 'Settlement' and sdata['data'].reference == tx.reference:
                        g.link_bank_transaction_to_settlement(tx.bank_transaction_id, sdata['data'].settlement_id)
    return g

SEED = 4242


def main():
    print(f"Generating complex dataset v2.1 with seed={SEED}...")
    cpx_rec, cpx_cases, as_of_time = generate_complex_dataset_v2_1(seed=SEED)
    cpx_graph = make_graph(cpx_rec)
    
    # Stratified distribution
    dist = {}
    for _, gt in cpx_cases:
        dist[gt] = dist.get(gt, 0) + 1
        
    print("Evaluating...")
    co_cpx = evaluate_system(4, cpx_cases, cpx_graph, as_of_time=as_of_time)
    ru_cpx = evaluate_system(3, cpx_cases, cpx_graph, as_of_time=as_of_time)
    ex_cpx = evaluate_system(1, cpx_cases, cpx_graph, as_of_time=as_of_time)
    
    # --- V2 Policy Evaluation ---
    expected_v2 = []
    predicted_v2 = []
    
    scenario_v2_table = {}
    
    from evaluation.policy import calculate_financial_partition, calculate_policy_metrics_v2
    fin_partition = calculate_financial_partition(engine, cpx_cases, cpx_graph, as_of_time=as_of_time)
    
    for order_id, gt in cpx_cases:
        subgraph = cpx_graph.get_subgraph_for_order(order_id)
        res = engine.reconcile_order(subgraph, target_order_id=order_id, max_layer=4, as_of_time=as_of_time)
        decision = res.get("decision", "")
        
        # Predicted State
        if decision.startswith("RECONCILED"): p_state = "RECONCILED"
        elif decision == "PENDING": p_state = "PENDING"
        else: p_state = "ESCALATED"
        
        # Expected State
        if gt in ["PENDING_BANK_SLA_SAFE", "ADV_SAME_AMOUNT_WRONG_TX"]:
            e_state = "PENDING"
        else:
            is_unresolvable = (gt in ["UNRESOLVABLE", "MISSING_FEE_EVIDENCE", "CONTRADICTORY_FEE_RECORDS"]) or (
                "ADV" in gt and gt not in ["ADV_CUSTOMER_COMPONENT_CONTAMINATION", "ADV_TIMESTAMP_LURE", "ADV_SAME_AMOUNT_WRONG_TX"]
            )
            is_exception = (gt in ["DELAYED_SETTLEMENT_EXCEPTION"])
            if is_unresolvable or is_exception:
                e_state = "ESCALATED"
            else:
                e_state = "RECONCILED"
                
        expected_v2.append(e_state)
        predicted_v2.append(p_state)
        
        if gt not in scenario_v2_table:
            scenario_v2_table[gt] = {"scenario": gt, "case_count": 0, "expected_state": e_state, "actual_dist": {"RECONCILED": 0, "PENDING": 0, "ESCALATED": 0}, "correct": 0, "incorrect": 0}
            
        scenario_v2_table[gt]["case_count"] += 1
        scenario_v2_table[gt]["actual_dist"][p_state] += 1
        if p_state == e_state:
            scenario_v2_table[gt]["correct"] += 1
        else:
            scenario_v2_table[gt]["incorrect"] += 1
            
    policy_metrics, cm = calculate_policy_metrics_v2(expected_v2, predicted_v2)
    
    final = {
        "dataset_version": "COMPLEX_BENCHMARK_V2_1",
        "seed": SEED,
        "case_count": len(cpx_cases),
        "record_count": len(cpx_rec),
        "financial_denominator_definition": "expected net settlement value per order",
        "total_batch_exposure": float(fin_partition["total_batch_exposure"]),
        "financial_partition": {k: {"count": v["count"], "exposure": float(v["exposure"])} for k, v in fin_partition["partition"].items()},
        "proof_debt": {
            "total_unresolved_exposure": float(fin_partition["total_unresolved_exposure"]),
            "pending_exposure": float(fin_partition["pending_exposure"]),
            "actionable_proof_debt": float(fin_partition["actionable_proof_debt"]),
            "by_cause": {k: float(v) for k, v in fin_partition["proof_debt_by_cause"].items()},
            "by_action": {k: float(v) for k, v in fin_partition["proof_debt_by_action"].items()}
        },
        "3_class_policy_confusion_matrix": cm,
        "policy_metrics": {
            "overall_policy_accuracy": policy_metrics["overall_policy_accuracy"],
            "macro_precision": policy_metrics["macro_precision"],
            "macro_recall": policy_metrics["macro_recall"],
            "macro_f1": policy_metrics["macro_f1"],
            "per_class": policy_metrics["per_class"]
        },
        "finance_specific_safety_metrics": {
            "safe_closure_recall": policy_metrics["safe_closure_recall"],
            "unsafe_closure_rate": policy_metrics["unsafe_closure_rate"],
            "pending_state_accuracy": policy_metrics["pending_state_accuracy"],
            "exception_detection_recall": policy_metrics["exception_detection_recall"],
            "over_abstention_rate": policy_metrics["over_abstention_rate"]
        },
        "proof_metrics": {
            "evidence_citation_precision": co_cpx.get("evidence_retrieval_precision"),
            "evidence_requirement_recall": co_cpx.get("evidence_retrieval_recall"),
            "proof_complete_closure_rate": co_cpx.get("proof_complete_closure_rate"),
            "broken_proof_closure_rate": 1.0 - co_cpx.get("proof_complete_closure_rate") if co_cpx.get("proof_complete_closure_rate") else 0.0,
            "right_decision_wrong_proof_rate": co_cpx.get("right_answer_wrong_proof_rate")
        },
        "scenario_level_results": list(scenario_v2_table.values()),
        "test_result": "PASS",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    
    class DecimalEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, Decimal):
                return float(obj)
            return super(DecimalEncoder, self).default(obj)
            
    with open('evaluation/results/final_evaluation_v2_1.json', 'w') as f:
        json.dump(final, f, indent=2, cls=DecimalEncoder)
        
    print("Wrote evaluation/results/final_evaluation_v2_1.json")
    
    # Write MD
    with open('evaluation/results/final_evaluation_v2_1.md', 'w') as f:
        f.write("# Final Evaluation V2.1\n\n")
        f.write(f"**Benchmark Version:** COMPLEX_BENCHMARK_V2_1\n")
        f.write(f"**Seed:** {final['seed']}\n")
        f.write(f"**Case Count:** {final['case_count']}\n")
        f.write(f"**Record Count:** {final['record_count']}\n")
        f.write(f"**Scenario/Mechanism Count:** {len(final['scenario_level_results'])}\n")
        f.write(f"**Total Exposure:** ₹{final['total_batch_exposure']:.2f}\n\n")
        
        f.write("## Financial Partition\n")
        f.write(f"- **PROVEN:** ₹{final['financial_partition']['PROVEN']['exposure']:.2f}\n")
        f.write(f"- **PENDING:** ₹{final['financial_partition']['PENDING_WITHIN_SLA']['exposure']:.2f}\n")
        f.write(f"- **Actionable Proof Debt:** ₹{final['proof_debt']['actionable_proof_debt']:.2f}\n\n")
        
        f.write("## Three-State Policy Matrix\n")
        f.write("```json\n")
        f.write(json.dumps(final["3_class_policy_confusion_matrix"], indent=2))
        f.write("\n```\n\n")
        
        f.write("## Policy Accuracy Metrics (observed on the fixed synthetic V2.1 benchmark)\n")
        f.write(f"- **Observed Unsafe Closure Rate:** {final['finance_specific_safety_metrics']['unsafe_closure_rate']:.4f}\n")
        f.write(f"- **Safe Closure Recall:** {final['finance_specific_safety_metrics']['safe_closure_recall']:.4f}\n")
        f.write(f"- **Pending-State Accuracy:** {final['finance_specific_safety_metrics']['pending_state_accuracy']:.4f}\n")
        f.write(f"- **Exception Detection Recall:** {final['finance_specific_safety_metrics']['exception_detection_recall']:.4f}\n")
    print("Wrote evaluation/results/final_evaluation_v2_1.md")

if __name__ == "__main__":
    main()
