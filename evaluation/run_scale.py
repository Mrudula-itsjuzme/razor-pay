import time
import json
import datetime
from evaluation.datagen import generate_dataset
from evaluation.run_v2_1 import make_graph
from main import engine
from reconciliation import ReconciliationEngine

def run_scale():
    print("Generating scale dataset (2500 cases)...")
    records, cases = generate_dataset(2500)
    print(f"Generated {len(records)} records for {len(cases)} cases.")
    
    start_t = time.perf_counter()
    g = make_graph(records)
    graph_time = time.perf_counter() - start_t
    print(f"Graph construction took {graph_time:.2f}s")
    
    latencies = []
    unresolved_cases = 0
    engine = ReconciliationEngine()
    
    start_eval = time.perf_counter()
    for order_id, ground_truth in cases:
        case_start = time.perf_counter()
        subgraph = g.get_subgraph_for_order(order_id)
        res = engine.reconcile_order(subgraph, target_order_id=order_id, max_layer=4)
        latencies.append(time.perf_counter() - case_start)
        if not res.get("decision", "").startswith("RECONCILED"):
            unresolved_cases += 1
            
    eval_time = time.perf_counter() - start_eval
    
    latencies.sort()
    
    def percentile(arr, p):
        if not arr: return 0
        k = (len(arr) - 1) * p
        f = int(k)
        c = f + 1
        if c >= len(arr): return arr[-1]
        return arr[f] + (arr[c] - arr[f]) * (k - f)
        
    p50 = percentile(latencies, 0.5) * 1000 if latencies else 0
    p95 = percentile(latencies, 0.95) * 1000 if latencies else 0
    
    scale_metrics = {
        "case_count": len(cases),
        "record_count": len(records),
        "total_time_seconds": eval_time,
        "throughput_cases_per_sec": len(cases) / eval_time if eval_time > 0 else 0,
        "p50_latency_ms": p50,
        "p95_latency_ms": p95,
        "unresolved_cases": unresolved_cases,
        "measurement_boundary": "Includes get_subgraph_for_order and reconcile_order for each case sequentially. Excludes full graph construction.",
        "graph_build_time_seconds": graph_time,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    
    with open("evaluation/results/scale_benchmark.json", "w") as f:
        json.dump(scale_metrics, f, indent=2)
        
    print("Wrote evaluation/results/scale_benchmark.json")

if __name__ == "__main__":
    run_scale()
