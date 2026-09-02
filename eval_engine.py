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
    total_debt = Decimal('0.00')
    pending = Decimal('0.00')
    missing = Decimal('0.00')
    ambiguous = Decimal('0.00')
    conflicting = Decimal('0.00')
    unresolvable = Decimal('0.00')
    
    for order_id, _ in cases:
        subgraph = graph_instance.get_subgraph_for_order(order_id)
        res = engine.reconcile_order(subgraph)
        decision = res["decision"]
        exposure = Decimal(res.get("expected_net", "0.00"))
        
        if decision in ["RECONCILED", "EXCEPTION"]:
            continue
            
        total_debt += exposure
        if decision == "PENDING":
            pending += exposure
        elif decision == "ESCALATED":
            reason = res.get("reason", "")
            if "conflicting" in reason.lower() or "duplicate" in reason.lower() or "ambiguous" in reason.lower():
                conflicting += exposure
            elif "ambiguous" in reason.lower():
                ambiguous += exposure
            elif "missing" in reason.lower() or "insufficient" in reason.lower():
                missing += exposure
            else:
                unresolvable += exposure
                
    return {
        "total": float(total_debt),
        "pending": float(pending),
        "missing": float(missing),
        "ambiguous": float(ambiguous),
        "conflicting": float(conflicting),
        "unresolvable": float(unresolvable)
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
            res = engine.reconcile_order(subgraph)
            
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
            
            res = engine.reconcile_order(degraded_subgraph)
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
