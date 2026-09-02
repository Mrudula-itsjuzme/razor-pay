import json
with open("final_complex_report.json") as f:
    d = json.load(f)
print(json.dumps(d["G"]["close_books"], indent=2))
