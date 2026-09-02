from datagen import generate_complex_dataset
records, cases = generate_complex_dataset()
for i in range(30015, 30020):
    for r in records:
        if type(r).__name__ == "Settlement" and r.settlement_id == f"set_{i}":
            print(i, r.initiated_at)
