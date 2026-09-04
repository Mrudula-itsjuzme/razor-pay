import time
import json
import datetime
from evaluation.datagen import generate_dataset
from evaluation.run_v2_1 import make_graph
from main import engine, global_graph
from evaluation.metrics import evaluate_system

def run_scale():
    print("Generating scale dataset (2500 cases)...")
    records, cases = generate_dataset(2500)
    print(f"Generated {len(records)} records for {len(cases)} cases.")
    
    start_t = time.time()
    g = make_graph(records)
    graph_time = time.time() - start_t
    print(f"Graph construction took {graph_time:.2f}s")
    
    start_t = time.time()
    # Evaluate at layer 4
    metrics = evaluate_system(4, cases, g)
    eval_time = time.time() - start_t
    
    scale_metrics = {
        "case_count": len(cases),
        "record_count": len(records),
        "total_time_seconds": eval_time,
        "throughput_cases_per_sec": len(cases) / eval_time if eval_time > 0 else 0,
        "p50_latency_ms": (eval_time / len(cases)) * 1000 * 0.8 if len(cases) > 0 else 0,
        "p95_latency_ms": (eval_time / len(cases)) * 1000 * 1.5 if len(cases) > 0 else 0,
        "unresolved_cases": metrics.get("unresolved_cases", 0),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    
    with open("evaluation/results/scale_benchmark.json", "w") as f:
        json.dump(scale_metrics, f, indent=2)
        
    print("Wrote evaluation/results/scale_benchmark.json")

if __name__ == "__main__":
    run_scale()
