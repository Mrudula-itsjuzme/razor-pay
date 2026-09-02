from typing import List, Dict, Tuple
from decimal import Decimal
import time
from models import *
from graph import ProvenanceGraph
from reconciliation import ReconciliationEngine

def get_failure_category(ground_truth: str, decision: str, is_unresolvable: bool, is_exception: bool, res: dict):
    if decision.startswith("RECONCILED"):
        if is_unresolvable or is_exception:
            if "ADV" in ground_truth:
                if "CURRENCY" in ground_truth:
                    return "UNSAFE_CLOSURE_CURRENCY_MISMATCH"
                elif "WRONG" in ground_truth:
                    return "UNSAFE_CLOSURE_WRONG_PROVENANCE"
                elif "CONTRADICTION" in ground_truth or "DUPLICATE" in ground_truth:
                    return "CONTRADICTION_FAILURE"
            return "UNSAFE_CLOSURE"
        return "NONE"
    elif decision.startswith("EXCEPTION"):
        if is_exception:
            return "NONE"
        else:
            return "UNNECESSARY_ABSTENTION"
    else:
        if is_unresolvable or is_exception:
            return "NONE"
        else:
            return "UNNECESSARY_ABSTENTION"

def calculate_proof_debt(engine, cases, graph_instance):
    total_unresolved = Decimal('0.00')
    pending_exposure = Decimal('0.00')
    actionable_proof_debt = Decimal('0.00')
    
    by_cause = {}
    by_action = {}
    top_cases = []
    
    for order_id, _ in cases:
        subgraph = graph_instance.get_subgraph_for_order(order_id)
        res = engine.reconcile_order(subgraph, target_order_id=order_id, max_layer=4)
        decision = res.get("decision", "")
        exposure = Decimal(res.get("expected_net", "0.00"))
        
        if decision.startswith("RECONCILED"):
            continue
            
        total_unresolved += exposure
        exc_details = res.get("exception_details", {})
        exc_type = exc_details.get("exception_type", "UNKNOWN")
        exc_subtype = exc_details.get("exception_subtype", "UNKNOWN")
        action = exc_details.get("recommended_action", "Manual human review required.")
        
        if exc_type == "PENDING_EVIDENCE":
            pending_exposure += exposure
        else:
            actionable_proof_debt += exposure
            
            by_cause[exc_subtype] = by_cause.get(exc_subtype, Decimal('0.00')) + exposure
            by_action[action] = by_action.get(action, Decimal('0.00')) + exposure
            
            top_cases.append({
                "case_id": order_id,
                "exposure": exposure,
                "subtype": exc_subtype,
                "action": action
            })
            
    # Sort top cases by exposure descending, take top 5
    top_cases.sort(key=lambda x: x["exposure"], reverse=True)
    top_cases_list = [{"case_id": c["case_id"], "exposure": float(c["exposure"]), "subtype": c["subtype"], "action": c["action"]} for c in top_cases[:5]]
                
    return {
        "total_unresolved_exposure": float(total_unresolved),
        "pending_exposure": float(pending_exposure),
        "actionable_proof_debt": float(actionable_proof_debt),
        "by_cause": {k: float(v) for k, v in by_cause.items()},
        "by_action": {k: float(v) for k, v in by_action.items()},
        "top_cases": top_cases_list
    }

def safe_automation_frontier(engine, cases, graph_instance):
    # Simulate different tolerance or completeness thresholds
    # We will just simulate match_confidence requirements
    results = []
    
    for req_completeness in [0.0, 0.5, 0.8, 1.0]:
        auto_closed = 0
        unsafe_closed = 0
        total_cases = len(cases)
        
        for order_id, ground_truth in cases:
            subgraph = graph_instance.get_subgraph_for_order(order_id)
            res = engine.reconcile_order(subgraph, target_order_id=order_id)
            
            decision = res["decision"]
            completeness = res.get("proof_completeness", 0)
            is_bad = ground_truth in ["UNRESOLVABLE", "MISSING_FEE_EVIDENCE"] or "ADV" in ground_truth
            
            if completeness >= req_completeness and res.get("match_confidence", 0) > 0.9:
                auto_closed += 1
                if is_bad:
                    unsafe_closed += 1
                    
        results.append({
            "threshold": f"Completeness >= {req_completeness}",
            "auto_closure_rate": auto_closed / total_cases if total_cases > 0 else 0,
            "unsafe_closure_rate": unsafe_closed / auto_closed if auto_closed > 0 else 0
        })
        
    return results

def evidence_degradation_experiment(engine, base_cases, graph_instance):
    results = []
    # Test 100%, 80%, 60%, 40%, 20%, 0% retention
    for retention in [1.0, 0.8, 0.6, 0.4, 0.2, 0.0]:
        auto_closed = 0
        unsafe_closed = 0
        correct_abstention = 0
        proof_complete_closed = 0
        human_review = 0
        total_cases = len(base_cases)
        
        for order_id, ground_truth in base_cases:
            subgraph = graph_instance.get_subgraph_for_order(order_id)
            
            # Degrade
            nodes_to_remove = []
            for n, d in subgraph.nodes(data=True):
                if d.get("type") in ["BankTransaction", "LedgerEntry", "Refund", "Fee", "Tax", "Payment"]:
                    # pseudo-random deterministic degradation
                    if (hash(n) % 100) / 100.0 > retention:
                        nodes_to_remove.append(n)
            
            degraded_subgraph = subgraph.copy()
            degraded_subgraph.remove_nodes_from(nodes_to_remove)
            
            res = engine.reconcile_order(degraded_subgraph, target_order_id=order_id)
            if "decision" not in res:
                continue
            decision = res["decision"]
            is_bad = ground_truth in ["UNRESOLVABLE", "MISSING_FEE_EVIDENCE"] or "ADV" in ground_truth
            completeness = res.get("proof_completeness", 0)
            
            if decision.startswith("RECONCILED"):
                auto_closed += 1
                if is_bad:
                    unsafe_closed += 1
                if completeness == 1.0:
                    proof_complete_closed += 1
            else:
                human_review += 1
                if is_bad:
                    correct_abstention += 1
                    
        unresolvable_count = sum(1 for c in base_cases if c[1] in ["UNRESOLVABLE", "MISSING_FEE_EVIDENCE"] or "ADV" in c[1])
                    
        results.append({
            "retention": retention,
            "auto_closure_rate": auto_closed / total_cases if total_cases > 0 else 0,
            "correct_abstention_rate": correct_abstention / unresolvable_count if unresolvable_count > 0 else 1.0,
            "unsafe_closure_rate": unsafe_closed / auto_closed if auto_closed > 0 else 0,
            "proof_complete_closure_rate": proof_complete_closed / auto_closed if auto_closed > 0 else 1.0,
            "human_review_rate": human_review / total_cases if total_cases > 0 else 0
        })
        
    return results
def calculate_policy_metrics_v2(expected_list, predicted_list):
    """
    Computes a 3-class confusion matrix for ['RECONCILED', 'PENDING', 'ESCALATED']
    and returns macro/per-class metrics, plus finance-specific metrics.
    """
    classes = ["RECONCILED", "PENDING", "ESCALATED"]
    
    # Confusion matrix
    cm = {c: {c_pred: 0 for c_pred in classes} for c in classes}
    for e, p in zip(expected_list, predicted_list):
        cm[e][p] += 1
        
    metrics = {}
    total = len(expected_list)
    correct = sum(cm[c][c] for c in classes)
    
    metrics["overall_policy_accuracy"] = correct / total if total > 0 else 0.0
    
    per_class = {}
    for c in classes:
        tp = cm[c][c]
        fp = sum(cm[true_c][c] for true_c in classes if true_c != c)
        fn = sum(cm[c][pred_c] for pred_c in classes if pred_c != c)
        support = sum(cm[c].values())
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        per_class[c] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support
        }
        
    metrics["per_class"] = per_class
    
    # Macro metrics
    metrics["macro_precision"] = sum(pc["precision"] for pc in per_class.values()) / 3
    metrics["macro_recall"] = sum(pc["recall"] for pc in per_class.values()) / 3
    metrics["macro_f1"] = sum(pc["f1"] for pc in per_class.values()) / 3
    
    # Finance specific metrics
    # safe_closure_recall = RECONCILED recall
    metrics["safe_closure_recall"] = per_class["RECONCILED"]["recall"]
    
    # unsafe_closure_rate = (false positives for RECONCILED when expected ESCALATED) / support of ESCALATED? 
    # Or just total false closures / total expected non-closures?
    expected_abstain = per_class["ESCALATED"]["support"]
    unsafe_closures = cm["ESCALATED"]["RECONCILED"]
    metrics["unsafe_closure_rate"] = unsafe_closures / expected_abstain if expected_abstain > 0 else 0.0
    
    metrics["pending_state_accuracy"] = per_class["PENDING"]["recall"]
    metrics["exception_detection_recall"] = per_class["ESCALATED"]["recall"]
    
    # over_abstention_rate = predicted ESCALATED when expected RECONCILED
    expected_reconcile = per_class["RECONCILED"]["support"]
    over_abstentions = cm["RECONCILED"]["ESCALATED"] + cm["RECONCILED"]["PENDING"] # Any abstention on safe case
    metrics["over_abstention_rate"] = over_abstentions / expected_reconcile if expected_reconcile > 0 else 0.0
    
    return metrics, cm
def calculate_financial_partition(engine, cases, graph_instance):
    from decimal import Decimal
    close_books_buckets = {
        "PROVEN": {"count": 0, "exposure": Decimal('0.0')},
        "PENDING_WITHIN_SLA": {"count": 0, "exposure": Decimal('0.0')},
        "MISSING_EVIDENCE": {"count": 0, "exposure": Decimal('0.0')},
        "CONFLICTING_EVIDENCE": {"count": 0, "exposure": Decimal('0.0')},
        "AMBIGUOUS_PROVENANCE": {"count": 0, "exposure": Decimal('0.0')},
        "ACCOUNTING_MISMATCH": {"count": 0, "exposure": Decimal('0.0')},
        "TEMPORAL_EXCEPTION": {"count": 0, "exposure": Decimal('0.0')},
        "UNRESOLVABLE": {"count": 0, "exposure": Decimal('0.0')},
        "UNCLASSIFIED": {"count": 0, "exposure": Decimal('0.0')}
    }
    
    total_batch_exposure = Decimal('0.0')
    
    # Store proof debt subsets
    by_cause = {}
    by_action = {}
    top_cases = []
    
    for order_id, _ in cases:
        subgraph = graph_instance.get_subgraph_for_order(order_id)
        res = engine.reconcile_order(subgraph, target_order_id=order_id, max_layer=4)
        exposure = Decimal(res.get("expected_net", "0.00"))
        
        total_batch_exposure += exposure
        
        decision = res.get("decision", "")
        if decision.startswith("RECONCILED") and res.get("proof_completeness", 0) == 1.0:
            close_books_buckets["PROVEN"]["count"] += 1
            close_books_buckets["PROVEN"]["exposure"] += exposure
        else:
            exc_details = res.get("exception_details", {})
            exc_type = exc_details.get("exception_type", "")
            exc_subtype = exc_details.get("exception_subtype", "UNKNOWN")
            action = exc_details.get("recommended_action", "Manual human review required.")
            
            if exc_type == "PENDING_EVIDENCE":
                bucket = "PENDING_WITHIN_SLA"
            elif exc_type == "MISSING_EVIDENCE":
                bucket = "MISSING_EVIDENCE"
            elif exc_type == "CONFLICTING_EVIDENCE":
                bucket = "CONFLICTING_EVIDENCE"
            elif exc_type == "AMBIGUOUS_PROVENANCE":
                bucket = "AMBIGUOUS_PROVENANCE"
            elif exc_type == "ACCOUNTING_MISMATCH":
                bucket = "ACCOUNTING_MISMATCH"
            elif exc_type == "TEMPORAL_EXCEPTION":
                bucket = "TEMPORAL_EXCEPTION"
            elif exc_type == "UNRESOLVABLE":
                bucket = "UNRESOLVABLE"
            else:
                bucket = "UNCLASSIFIED"
                
            close_books_buckets[bucket]["count"] += 1
            close_books_buckets[bucket]["exposure"] += exposure
            
            if bucket != "PENDING_WITHIN_SLA":
                by_cause[exc_subtype] = by_cause.get(exc_subtype, Decimal('0.0')) + exposure
                by_action[action] = by_action.get(action, Decimal('0.0')) + exposure
                top_cases.append({
                    "case_id": order_id,
                    "exposure": exposure,
                    "subtype": exc_subtype,
                    "action": action
                })
                
    proven = close_books_buckets["PROVEN"]["exposure"]
    total_unresolved = total_batch_exposure - proven
    pending = close_books_buckets["PENDING_WITHIN_SLA"]["exposure"]
    actionable_proof_debt = (
        close_books_buckets["MISSING_EVIDENCE"]["exposure"] +
        close_books_buckets["CONFLICTING_EVIDENCE"]["exposure"] +
        close_books_buckets["AMBIGUOUS_PROVENANCE"]["exposure"] +
        close_books_buckets["ACCOUNTING_MISMATCH"]["exposure"] +
        close_books_buckets["TEMPORAL_EXCEPTION"]["exposure"] +
        close_books_buckets["UNRESOLVABLE"]["exposure"] +
        close_books_buckets["UNCLASSIFIED"]["exposure"]
    )
    
    # Assertions
    assert sum(b["exposure"] for b in close_books_buckets.values()) == total_batch_exposure
    assert total_unresolved == (total_batch_exposure - proven)
    assert pending + actionable_proof_debt == total_unresolved
    
    top_cases.sort(key=lambda x: x["exposure"], reverse=True)
    
    return {
        "total_batch_exposure": total_batch_exposure,
        "total_unresolved_exposure": total_unresolved,
        "actionable_proof_debt": actionable_proof_debt,
        "pending_exposure": pending,
        "partition": close_books_buckets,
        "proof_debt_by_cause": by_cause,
        "proof_debt_by_action": by_action,
        "proof_debt_top_cases": top_cases[:5]
    }
