# Finance Controller

"Don't match transactions. Prove what happened to the money."

## What it does
Reconstructs what happened to the money, automatically closes only what the evidence proves, and turns everything else into an actionable proof gap.

## Why evidence/provenance matters
Amounts matching does not prove they represent the same money. Every automated close must carry a strict reconciliation proof tied to explicit provenance and temporal validity.

## One killer example
- **Complete evidence** -> RECONCILED
- **Same arithmetic with missing fee** -> ESCALATED
- **Same-amount wrong UTR** -> ignored as unrelated evidence
- **Future-dated bank record** -> ESCALATED

## Architecture
- Deterministic Reconciliation Gate
- Strict Evidence Contracts
- Provenance Graph
- AI Investigator (Strictly Sandboxed)

## How AI is bounded
| AI MAY: | AI MAY NOT: |
| --- | --- |
| - rank evidence-backed hypotheses<br>- explain proof gaps<br>- suggest investigation steps<br>- summarize exceptions | - perform authoritative accounting arithmetic<br>- fabricate evidence<br>- authorize closure<br>- override temporal validity<br>- override proof contracts<br>- convert hypotheses into facts |

The model may improve investigation quality. It does not determine accounting truth.

## Benchmark results
**V2.1 Fixed Synthetic Benchmark**
- **Case Count:** 105 cases across 21 adversarial/clean scenario families
- **Observed Unsafe Closure Count:** 0
- **False Auto-Closure Rate:** 0.0%
- **Safe Closure Recall:** 100%
- **Pending-State Accuracy:** 100%
- **Exception Detection Recall:** 100%

*Note: These are results on a fixed synthetic benchmark, NOT evidence of production accuracy. See [Benchmark Methodology](docs/BENCHMARK_METHODOLOGY.md) for full context.*

## Scale benchmark
Includes `get_subgraph_for_order` and `reconcile_order` for each case sequentially. Excludes full graph construction.
- **Case Count:** 2,500
- **Record Count:** 20,079
- **Graph Build Time:** 10.40s
- **Measured Reconciliation Time:** 0.51s
- **Throughput:** ~4895 cases/sec
- **p50 Latency:** 0.18ms
- **p95 Latency:** 0.26ms

## Run locally
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pytest -q
PYTHONPATH=. python evaluation/run_v2_1.py
PYTHONPATH=. python evaluation/run_scale.py
uvicorn main:app --host 127.0.0.1 --port 8000
```

## Tests
Tested thoroughly against adversarial scenarios via `pytest` testing suite.

## Limitations
- Synthetic financial data
- No FX conversion
- No live production merchant validation
- Strict temporal ordering may over-flag valid delayed distributed events

## Failure Log
See the detailed [Failure Log](docs/FAILURE_LOG.md) detailing the hostile-audit discoveries and fixes.
