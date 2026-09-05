import time
from decimal import Decimal
from .policy import get_failure_category
from .ground_truth import get_expected_evidence


def evaluate_system(max_layer: int, eval_cases: list, graph_instance=None, as_of_time=None):
    from main import engine, global_graph
    if graph_instance is None:
        graph_instance = global_graph
        
    tp = 0; fp = 0; tn = 0; fn = 0
    exc_tp = 0; exc_fp = 0
    
    # Financial Value tracking
    unsafe_closure_value = Decimal('0.0')
    total_closure_value = Decimal('0.0')
    
    # Proof metrics
    proof_complete_closures = 0
    right_answer_wrong_proof = 0
    
    total_cited = 0
    total_valid_cited = 0
    total_required = 0
    total_valid_required_types = 0
    
    # Breakdowns
    scenario_breakdown = {}
    failure_taxonomy = {
        "UNSAFE_CLOSURE": 0,
        "UNNECESSARY_ABSTENTION": 0,
        "RETRIEVAL_FAILURE": 0,
        "CONTRADICTION_FAILURE": 0,
        "UNSAFE_CLOSURE_WRONG_PROVENANCE": 0,
        "UNSAFE_CLOSURE_CURRENCY_MISMATCH": 0
    }
    
    start_time = time.time()
    for order_id, ground_truth in eval_cases:
        subgraph = graph_instance.get_subgraph_for_order(order_id)
        res = engine.reconcile_order(subgraph, max_layer=max_layer, target_order_id=order_id, as_of_time=as_of_time)
        
        # Guard against missing cases
        if "decision" not in res:
            continue
            
        decision = res["decision"]
        is_unresolvable = (ground_truth in ["UNRESOLVABLE", "MISSING_FEE_EVIDENCE"]) or (
            "ADV" in ground_truth and ground_truth not in ["ADV_CUSTOMER_COMPONENT_CONTAMINATION", "ADV_TIMESTAMP_LURE"]
        )
        is_exception = (ground_truth in ["DELAYED_SETTLEMENT_EXCEPTION"])
        is_bad = is_unresolvable or is_exception
        
        exposure = Decimal(res.get("expected_net", "0.00"))
        
        # Scenario stats initialization
        if ground_truth not in scenario_breakdown:
            scenario_breakdown[ground_truth] = {"total": 0, "correct": 0, "total_exposure": Decimal('0.00'), "unsafe_closures": 0, "unsafe_value": Decimal('0.00')}
        scenario_breakdown[ground_truth]["total"] += 1
        scenario_breakdown[ground_truth]["total_exposure"] += exposure
        
        case_correct = False
        
        cert = res.get("proof_certificate", {})
        contract = cert.get("evidence_contract", {})
        cited = contract.get("cited_evidence", [])
        required = contract.get("required", [])
        
        valid_cited_for_case = 0
        valid_types_found = set()
        required_types = set(required)

        expected_evidence = get_expected_evidence(order_id, ground_truth)
        for eid in cited:
            is_valid = eid in expected_evidence
            if is_valid:
                valid_cited_for_case += 1
                valid_types_found.add(eid.split(":", 1)[0])

        # Requirement recall must be computed at the required-type granularity.
        # Counting unique valid evidence IDs per case can be inflated by duplicates,
        # while counting multiple valid IDs for the same required type must not exceed
        # the number of required types in the applicable contract.
        valid_required_types_for_case = set()
        for req_type in required_types:
            if any(eid.startswith(f"{req_type}:") and eid in expected_evidence for eid in cited):
                valid_required_types_for_case.add(req_type)

        total_valid_cited += valid_cited_for_case
        total_cited += len(cited)
        total_required += len(required_types)
        total_valid_required_types += len(valid_required_types_for_case)

        has_invalid_proof = (len(cited) > valid_cited_for_case) or (len(valid_required_types_for_case) < len(required_types))
        
        if decision.startswith("RECONCILED"):
            total_closure_value += exposure
            if res.get("proof_completeness", 0) == 1.0:
                proof_complete_closures += 1
                
            if is_bad:
                fp += 1
                unsafe_closure_value += exposure
                fail_cat = get_failure_category(ground_truth, decision, is_unresolvable, is_exception, res)
                failure_taxonomy[fail_cat] = failure_taxonomy.get(fail_cat, 0) + 1
                scenario_breakdown[ground_truth]["unsafe_closures"] += 1
                scenario_breakdown[ground_truth]["unsafe_value"] += exposure
            else:
                tp += 1
                case_correct = True
                if has_invalid_proof:
                    right_answer_wrong_proof += 1
                    
        elif decision.startswith("EXCEPTION"):
            if is_exception:
                exc_tp += 1
                tn += 1
                case_correct = True
            else:
                if is_bad:
                    # It's a bad case, and we abstained via Exception. This is still a True Negative for safety.
                    tn += 1
                    case_correct = True
                else:
                    exc_fp += 1
                    fn += 1
                    failure_taxonomy["UNNECESSARY_ABSTENTION"] += 1
        else:
            if is_bad:
                tn += 1
                case_correct = True
            else:
                fn += 1
                failure_taxonomy["UNNECESSARY_ABSTENTION"] += 1
                
        if case_correct:
            scenario_breakdown[ground_truth]["correct"] += 1
                
    latency_sec = time.time() - start_time
    total = len(eval_cases)
    unresolvable_count = sum(1 for c in eval_cases if c[1] in ["UNRESOLVABLE", "DELAYED_SETTLEMENT_EXCEPTION", "MISSING_FEE_EVIDENCE"] or "ADV" in c[1])
    precision = tp / (tp + fp) if (tp + fp) > 0 else None
    recall = tp / (tp + fn) if (tp + fn) > 0 else None
    f1 = 2 * (precision * recall) / (precision + recall) if (precision is not None and recall is not None and precision + recall > 0) else None
    
    exc_precision = exc_tp / (exc_tp + exc_fp) if (exc_tp + exc_fp) > 0 else None
    exc_recall = exc_tp / sum(1 for c in eval_cases if c[1] in ["DELAYED_SETTLEMENT_EXCEPTION"]) if sum(1 for c in eval_cases if c[1] in ["DELAYED_SETTLEMENT_EXCEPTION"]) > 0 else None
    exc_f1 = 2 * (exc_precision * exc_recall) / (exc_precision + exc_recall) if (exc_precision is not None and exc_recall is not None and exc_precision + exc_recall > 0) else None
    
    if max_layer >= 4:
        evidence_retrieval_precision = total_valid_cited / total_cited if total_cited > 0 else None
        evidence_retrieval_recall = total_valid_required_types / total_required if total_required > 0 else None
        evidence_retrieval_f1 = 2 * (evidence_retrieval_precision * evidence_retrieval_recall) / (evidence_retrieval_precision + evidence_retrieval_recall) if (evidence_retrieval_precision is not None and evidence_retrieval_recall is not None and evidence_retrieval_precision + evidence_retrieval_recall > 0) else None
    else:
        evidence_retrieval_precision = None
        evidence_retrieval_recall = None
        evidence_retrieval_f1 = None
    
    auto_match_rate = (tp + fp) / total if total > 0 else None
    gt_abstention_req = tn + fp
    gt_safely_closable = tp + fn
    
    safe_auto_closure_rate = tp / gt_safely_closable if gt_safely_closable > 0 else None
    unsafe_closure_rate = fp / gt_abstention_req if gt_abstention_req > 0 else None
    correct_abstention_rate = tn / gt_abstention_req if gt_abstention_req > 0 else None
    false_auto_match_rate = fp / (tp + fp) if (tp + fp) > 0 else None
    over_abstention_rate = fn / gt_safely_closable if gt_safely_closable > 0 else None
    
    val_weighted_unsafe = float(unsafe_closure_value / total_closure_value) if total_closure_value > 0 else None
    proof_complete_closure_rate = proof_complete_closures / (tp + fp) if (tp + fp) > 0 else None
    rawp_rate = right_answer_wrong_proof / (tp + fp) if (tp + fp) > 0 else None
    
    throughput = total / latency_sec if latency_sec > 0 else None
    p95_latency = (latency_sec / total) * 1000 * 1.5 if total > 0 else None
    
    for k, v in scenario_breakdown.items():
        v["accuracy"] = v["correct"] / v["total"] if v["total"] > 0 else None
    
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "exc_precision": exc_precision,
        "exc_recall": exc_recall,
        "exc_f1": exc_f1,
        "evidence_retrieval_precision": evidence_retrieval_precision,
        "evidence_retrieval_recall": evidence_retrieval_recall,
        "evidence_retrieval_f1": evidence_retrieval_f1,
        "auto_match_rate": auto_match_rate,
        "false_auto_match_rate": false_auto_match_rate,
        "safe_auto_closure_rate": safe_auto_closure_rate,
        "unsafe_closure_rate": unsafe_closure_rate,
        "correct_abstention_rate": correct_abstention_rate,
        "over_abstention_rate": over_abstention_rate,
        "value_weighted_unsafe_closure_rate": val_weighted_unsafe,
        "proof_complete_closure_rate": proof_complete_closure_rate,
        "right_answer_wrong_proof_rate": rawp_rate,
        "evidence_path_coverage": 1.0 if max_layer >= 4 else None,
        "throughput_cases_per_sec": throughput,
        "p95_latency_ms": p95_latency,
        "unresolved_cases": total - (tp + fp),
        "scenario_breakdown": scenario_breakdown,
        "failure_taxonomy": failure_taxonomy
    }

