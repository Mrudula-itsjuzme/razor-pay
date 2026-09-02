import json
from decimal import Decimal
from datagen import generate_complex_dataset
from run_complex_eval import make_graph
from main import engine

cpx_rec, cpx_cases = generate_complex_dataset()
cpx_graph = make_graph(cpx_rec)

for order_id, gt in cpx_cases:
    subgraph = cpx_graph.get_subgraph_for_order(order_id)
    res = engine.reconcile_order(subgraph, target_order_id=order_id, max_layer=4)
    exposure = Decimal(res.get("expected_net", "0.00"))
    
    # Eval engine logic
    is_eval_pending = False
    if not res.get("decision", "").startswith("RECONCILED"):
        exc_type = res.get("exception_details", {}).get("exception_type", "")
        if exc_type == "PENDING_EVIDENCE":
            is_eval_pending = True
            
    # Run complex eval logic
    is_complex_pending = False
    if res.get("decision", "").startswith("RECONCILED") and res.get("proof_completeness", 0) == 1.0:
        pass
    else:
        exc_type = res.get("exception_details", {}).get("exception_type", "")
        if exc_type == "PENDING_EVIDENCE":
            is_complex_pending = True

    if is_eval_pending != is_complex_pending:
        print(f"Diff 1 on {order_id}!")
        
    if exposure > 0:
        print(order_id, is_eval_pending, exposure)
