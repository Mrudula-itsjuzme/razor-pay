from datagen import generate_complex_dataset
from run_complex_eval import make_graph
from main import engine

records, cases = generate_complex_dataset()
g = make_graph(records)

sub = g.get_subgraph_for_order("30015")
res = engine.reconcile_order(sub, target_order_id="30015", max_layer=4)
import json
print(json.dumps(res, indent=2))
