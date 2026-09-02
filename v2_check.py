import json
from datagen import generate_complex_dataset
from run_complex_eval import make_graph
from main import engine

cpx_rec, cpx_cases = generate_complex_dataset()
cpx_graph = make_graph(cpx_rec)
for order_id, gt in cpx_cases:
    subgraph = cpx_graph.get_subgraph_for_order(order_id)
    res = engine.reconcile_order(subgraph, target_order_id=order_id, max_layer=4)
    decision = res.get("decision", "")
    is_bad_v1 = gt in ["UNRESOLVABLE", "MISSING_FEE_EVIDENCE"] or "ADV" in gt
    if decision.startswith("RECONCILED") and is_bad_v1:
        print(order_id, gt, res.get("reason"))
