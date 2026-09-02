from datagen import generate_adversarial_case
from datetime import datetime
from graph import ProvenanceGraph
from main import engine

base_time = datetime(2026, 8, 5, 10, 0, 0)
r, c = generate_adversarial_case(1, "ADV_TIMESTAMP_LURE", base_time)
g = ProvenanceGraph()
from models import Order, Payment, Refund, Fee, Tax, Settlement, BankTransaction
for rec in r:
    if isinstance(rec, Order): g.add_order(rec)
    elif isinstance(rec, Payment): g.add_payment(rec)
    elif isinstance(rec, Fee): g.add_fee(rec)
    elif isinstance(rec, Tax): g.add_tax(rec)
    elif isinstance(rec, BankTransaction): g.add_bank_transaction(rec)
    elif isinstance(rec, Settlement): g.add_settlement(rec, [])
subgraph = g.get_subgraph_for_order(c["order_id"])
res = engine.reconcile_order(subgraph, target_order_id=c["order_id"])
print(res["decision"])
print(res.get("exception_details", {}))
