from datagen import generate_complex_dataset
from run_complex_eval import make_graph
from main import engine, evaluate_system

records, cases = generate_complex_dataset()
g = make_graph(records)

safely_automatable_value = 0.0
safe_automated_value = {"exact": 0.0, "rules": 0.0, "controller": 0.0}
unsafe_automated_value = {"exact": 0.0, "rules": 0.0, "controller": 0.0}
over_abstained_value = {"exact": 0.0, "rules": 0.0, "controller": 0.0}

for order_id, gt in cases:
    is_unresolvable = (gt in ["UNRESOLVABLE", "MISSING_FEE_EVIDENCE"]) or (
        "ADV" in gt and gt not in ["ADV_CUSTOMER_COMPONENT_CONTAMINATION", "ADV_TIMESTAMP_LURE"]
    )
    is_exception = (gt in ["DELAYED_SETTLEMENT_EXCEPTION"])
    is_bad = is_unresolvable or is_exception

    subgraph = g.get_subgraph_for_order(order_id)
    
    # exact
    res_ex = engine.reconcile_order(subgraph, max_layer=1, target_order_id=order_id)
    exp_net = float(res_ex.get("expected_net", 0))
    if not is_bad: safely_automatable_value += exp_net
    
    for sys, lay in [("exact", 1), ("rules", 3), ("controller", 4)]:
        res = engine.reconcile_order(subgraph, max_layer=lay, target_order_id=order_id)
        dec = res.get("decision", "")
        if dec.startswith("RECONCILED"):
            if is_bad: unsafe_automated_value[sys] += exp_net
            else: safe_automated_value[sys] += exp_net
        else:
            if not is_bad: over_abstained_value[sys] += exp_net

print(f"safely_automatable_value: {safely_automatable_value}")
print(f"safe_automated_value: {safe_automated_value}")
print(f"unsafe_automated_value: {unsafe_automated_value}")
print(f"over_abstained_value: {over_abstained_value}")
