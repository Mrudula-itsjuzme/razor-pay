from main import app, engine, global_graph
from datagen import generate_demo_dataset
from graph import ProvenanceGraph
from models import Order, Payment, Refund, Fee, Tax, Settlement, BankTransaction

global_graph = ProvenanceGraph()
records, cases = generate_demo_dataset()
for r in records:
    if isinstance(r, Order): global_graph.add_order(r)
    elif isinstance(r, Payment): global_graph.add_payment(r)
    elif isinstance(r, Refund): global_graph.add_refund(r)
    elif isinstance(r, Fee): global_graph.add_fee(r)
    elif isinstance(r, Tax): global_graph.add_tax(r)
    elif isinstance(r, BankTransaction): global_graph.add_bank_transaction(r)
    elif isinstance(r, Settlement): global_graph.add_settlement(r, [])

subgraph = global_graph.get_subgraph_for_order("6000")
print("EVAL TIME:", engine.evaluation_time)
res = engine.reconcile_order(subgraph, target_order_id="6000", max_layer=4)
print(res["decision"])
print(res.get("layers_run", []))
print(res.get("exception_details", {}))
