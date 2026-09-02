from datagen_v2_1 import generate_case_v2_1
from datetime import datetime

base_time = datetime(2026, 8, 1, 10, 0, 0)
as_of_time = datetime(2026, 8, 15, 12, 0, 0)

# Simulate before
print("BEFORE (i*5)")
for i in [30000, 30104]:
    # manual calculation
    created_at = base_time + datetime.timedelta(minutes=i*5) if hasattr(datetime, "timedelta") else base_time + __import__("datetime").timedelta(minutes=i*5)
    print(f"Order {i}: {created_at}")

# Simulate after
print("AFTER ((i-30000)*5)")
for i in [30000, 30104]:
    case_index = i - 30000
    created_at = base_time + __import__("datetime").timedelta(minutes=case_index*5)
    print(f"Order {i}: {created_at}")
