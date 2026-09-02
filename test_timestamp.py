from datagen import generate_complex_dataset
records, cases = generate_complex_dataset()
for r in records:
    if type(r).__name__ == "Settlement" and r.settlement_id == "set_30015":
        print("Initiated at:", r.initiated_at)
