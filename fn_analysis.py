import json
from decimal import Decimal
import datetime
from datagen import generate_complex_dataset
from run_complex_eval import make_graph
from main import engine, evaluate_system

records, cases = generate_complex_dataset()
g = make_graph(records)

fns = []
for order_id, gt in cases:
    subgraph = g.get_subgraph_for_order(order_id)
    res = engine.reconcile_order(subgraph, max_layer=4, target_order_id=order_id)
    
    is_unresolvable = (gt in ["UNRESOLVABLE", "MISSING_FEE_EVIDENCE"]) or (
        "ADV" in gt and gt not in ["ADV_CUSTOMER_COMPONENT_CONTAMINATION", "ADV_TIMESTAMP_LURE"]
    )
    is_exception = (gt in ["DELAYED_SETTLEMENT_EXCEPTION"])
    is_bad = is_unresolvable or is_exception
    
    decision = res.get("decision", "")
    
    # FN is when it's safe (is_bad == False) but we don't RECONCILE
    # Wait, if is_bad == False, the system should RECONCILE.
    # What if decision == PENDING? Is that TN or FN?
    # In evaluate_system:
    if not is_bad and not decision.startswith("RECONCILED"):
        fns.append({
            "case_id": order_id,
            "scenario": gt,
            "decision": decision,
            "reason": res.get("reason", ""),
            "expected_net": str(res.get("expected_net", "0")),
            "observed": str(res.get("observed_settlement", "0")),
            "diff": str(res.get("difference", "0"))
        })

print(f"Total FNs: {len(fns)}")
grouped = {}
for fn in fns:
    scen = fn["scenario"]
    grouped.setdefault(scen, []).append(fn)

for scen, items in grouped.items():
    print(f"\nScenario: {scen} ({len(items)} cases)")
    print(items[0])
