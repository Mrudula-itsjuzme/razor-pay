import json
from datagen import generate_complex_dataset
from run_complex_eval import make_graph
from main import engine
from eval_engine import calculate_proof_debt

cpx_rec, cpx_cases = generate_complex_dataset()
cpx_graph = make_graph(cpx_rec)
print(json.dumps(calculate_proof_debt(engine, cpx_cases, cpx_graph), indent=2))
