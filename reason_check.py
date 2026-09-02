from datagen import generate_complex_dataset
from run_complex_eval import make_graph
from main import engine
records, cases = generate_complex_dataset()
g = make_graph(records)
for order_id, gt in cases:
    if gt in ["CONTRADICTORY_FEE_RECORDS", "ADV_DUPLICATE_UTR", "ADV_DUPLICATE_PAYMENT"]:
        subgraph = g.get_subgraph_for_order(order_id)
        res = engine.reconcile_order(subgraph, max_layer=4, target_order_id=order_id)
        print(gt, res.get("decision"), res.get("reason"), res.get("conflicting_evidence"))
