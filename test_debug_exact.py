from datagen import generate_complex_dataset
from run_complex_eval import make_graph
from main import engine

records, cases = generate_complex_dataset()
g = make_graph(records)

for order_id, gt in cases:
    if gt == "DELAYED_SETTLEMENT_EXCEPTION":
        sub = g.get_subgraph_for_order(order_id)
        res = engine.reconcile_order(sub, target_order_id=order_id, max_layer=4)
        print("DELAYED:", order_id, res.get("decision"))
    elif gt == "ADV_SAME_AMOUNT_WRONG_TX":
        sub = g.get_subgraph_for_order(order_id)
        res = engine.reconcile_order(sub, target_order_id=order_id, max_layer=4)
        print("ADV_WRONG_TX:", order_id, res.get("decision"))
