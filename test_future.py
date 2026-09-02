from datagen import generate_complex_dataset
from datetime import datetime
records, cases = generate_complex_dataset()
eval_time = datetime(2026, 8, 15)
for order_id, gt in cases:
    # Get settlement initiated_at
    sets = [r for r in records if type(r).__name__ == "Settlement" and r.settlement_id.replace("set_", "").replace("adv_", "").split("_")[0] == str(order_id).replace("adv_", "")]
    if not sets: continue
    s = sets[0]
    delta = (eval_time - s.initiated_at).total_seconds() / 86400.0
    if delta < 0:
        print(order_id, gt, delta)
