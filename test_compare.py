import json
from decimal import Decimal
from datagen import generate_complex_dataset
from run_complex_eval import make_graph, engine
from eval_engine import calculate_proof_debt

cpx_rec, cpx_cases = generate_complex_dataset()
cpx_graph = make_graph(cpx_rec)

debt = calculate_proof_debt(engine, cpx_cases, cpx_graph)

cb_pending = Decimal('0.0')
for order_id, _ in cpx_cases:
    subgraph = cpx_graph.get_subgraph_for_order(order_id)
    res = engine.reconcile_order(subgraph, target_order_id=order_id, max_layer=4)
    decision = res.get("decision", "")
    exposure = Decimal(res.get("expected_net", "0.00"))
    
    if not (decision.startswith("RECONCILED") and res.get("proof_completeness", 0) == 1.0):
        exc_type = res.get("exception_details", {}).get("exception_type", "")
        if exc_type == "PENDING_EVIDENCE":
            cb_pending += exposure

print("Proof Debt Pending:", debt["pending_exposure"])
print("Close Books Pending:", cb_pending)
