import json
from datagen import generate_complex_dataset
from run_complex_eval import make_graph
from main import engine

cpx_rec, cpx_cases = generate_complex_dataset()
cpx_graph = make_graph(cpx_rec)

v1_tp, v1_fp, v1_tn, v1_fn = 0, 0, 0, 0
v2_tp, v2_fp, v2_tn, v2_fn = 0, 0, 0, 0

for order_id, gt in cpx_cases:
    subgraph = cpx_graph.get_subgraph_for_order(order_id)
    res = engine.reconcile_order(subgraph, target_order_id=order_id, max_layer=4)
    decision = res.get("decision", "")
    
    # V1 evaluation
    is_bad_v1 = gt in ["UNRESOLVABLE", "MISSING_FEE_EVIDENCE"] or "ADV" in gt
    is_exc_v1 = gt == "DELAYED_SETTLEMENT_EXCEPTION"
    
    if decision.startswith("RECONCILED"):
        if is_bad_v1: v1_fp += 1
        else: v1_tp += 1
    elif decision.startswith("EXCEPTION"):
        if is_bad_v1 or is_exc_v1: v1_tn += 1
        else: v1_fn += 1
    else:
        if is_bad_v1 or is_exc_v1: v1_tn += 1
        else: v1_fn += 1
        
    # V2 evaluation
    is_bad_v2 = is_bad_v1 or gt == "CONTRADICTORY_FEE_RECORDS"
    is_exc_v2 = is_exc_v1
    
    if decision.startswith("RECONCILED"):
        if is_bad_v2: v2_fp += 1
        else: v2_tp += 1
    elif decision.startswith("EXCEPTION"):
        if is_bad_v2 or is_exc_v2: v2_tn += 1
        else:
            if gt == "PENDING_BANK_SLA_SAFE": v2_tn += 1 # Not a false negative if it correctly abstained!
            else: v2_fn += 1
    else:
        if is_bad_v2 or is_exc_v2: v2_tn += 1
        else:
            if gt == "PENDING_BANK_SLA_SAFE" and decision == "PENDING": v2_tn += 1 # Expected PENDING
            else: v2_fn += 1

print(f"V1: TP={v1_tp} FP={v1_fp} TN={v1_tn} FN={v1_fn}")
print(f"V2: TP={v2_tp} FP={v2_fp} TN={v2_tn} FN={v2_fn}")

