from datagen import generate_complex_dataset
records, cases = generate_complex_dataset()
for order_id, gt in cases:
    if gt == "PENDING_BANK_SLA_SAFE":
        order = [r for r in records if type(r).__name__ == "Order" and r.order_id == str(order_id)][0]
        set_ = [r for r in records if type(r).__name__ == "Settlement" and r.settlement_id == f"set_{order_id}"]
        if set_: print(gt, "Order:", order.created_at, "Set:", set_[0].initiated_at)
