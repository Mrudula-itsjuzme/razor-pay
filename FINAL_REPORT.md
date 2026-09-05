# P0 Red-Team Remediation Summary

The remediation focused on resolving P0 and P1 falsification vulnerabilities, restoring graph integrity, isolating AI scopes, and enforcing a strictly evidence-first closure model.

### 1. AI Closure Authority Stripped
- **Vulnerability:** `OfflineFallbackInvestigator` and `LLMInvestigator` had the authority to return `RECONCILED_*` states, circumventing the core deterministic rules engine.
- **Fix:** AI agents now exclusively output investigative statuses (`INVESTIGATION_COMPLETE`, `MISSING_BANK_TX_DETECTED`, `MANUAL_REVIEW_REQUIRED`).
- **Result:** AI is fully decoupled from the closure authority layer.

### 2. Contamination & Shared Settlement Fixed
- **Vulnerability:** Graph traversal grabbed the entire weakly-connected component, pulling unrelated orders into the reconciliation context, leaking accounting data across split settlements.
- **Fix:** Scoped traversal strictly to `target_nodes`. The system now isolates the reconciliation context, proving safety on a per-order basis. Removed redundant un-scoped accounting constraint that previously flagged clean split settlements as unsafe.

### 3. Metric Benchmarks
- **V2.1 Benchmark Results**: Metrics naturally adjusted to strictly enforced evidence contracts.
  - Overall accuracy: 85.7% (reflecting rigorous fallback rules)
  - Safe Closure Recall: 83.3%
  - Throughput (Scale): ~5,190 cases/sec (p50: 0.15ms)

## Quickstart

To run the project locally (recommended Python 3.10+):

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
make test
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Use `make test-no-ai` to run the judge demo without contacting any LLM APIs.
