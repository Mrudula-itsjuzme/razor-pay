from datagen import generate_case
from datetime import datetime
from graph import ProvenanceGraph
from main import engine

records, meta = generate_case(1, "DELAYED_SETTLEMENT_EXCEPTION", datetime(2026, 8, 14, 12, 0, 0))
g = ProvenanceGraph()
for r in records:
    if type(r).__name__ == "Order": g.add_order(r)
    elif type(r).__name__ == "Payment": g.add_payment(r)
    elif type(r).__name__ == "Settlement": g.add_settlement(r, [i for i in records if type(i).__name__ == "SettlementItem"])
    elif type(r).__name__ == "Fee": g.add_fee(r)
    elif type(r).__name__ == "Tax": g.add_tax(r)
    elif type(r).__name__ == "BankTransaction": g.add_bank_transaction(r)
    elif type(r).__name__ == "Refund": g.add_refund(r)

sub = g.get_subgraph_for_order(records[0].order_id)
res = engine.reconcile_order(sub, target_order_id=records[0].order_id, max_layer=4)
print("Decision:", res["decision"])
print("Reason:", res["reason"])
print("Exception details:", res.get("exception_details"))
print("Proof completeness:", res.get("proof_completeness"))
print("SLA Breached?", res.get("audit_trail", {}).get("broken_edges", []))
