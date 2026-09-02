import json

with open("final_complex_report.json") as f:
    data = json.load(f)

d = data["D"]
print(json.dumps(d, indent=2))
