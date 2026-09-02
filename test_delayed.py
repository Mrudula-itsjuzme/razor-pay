from datagen import generate_case
from datetime import datetime
records, meta = generate_case(1, "DELAYED_SETTLEMENT_EXCEPTION", datetime(2026, 8, 14, 12, 0, 0))
print([type(r).__name__ for r in records])
print("Settlement dates:", [s.initiated_at for s in records if type(s).__name__ == "Settlement"])
print("Order date:", [o.created_at for o in records if type(o).__name__ == "Order"])
