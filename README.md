# Razorpay Finance Controller

"Don't match transactions. Prove what happened to the money."

A deterministic, provenance-backed finance controller for Razorpay AI Buildathon (Track 04: AI Finance Controller). Reconstructs money lifecycles from raw financial events, closes only what evidence proves, and turns every exception into an actionable proof gap.

---

## The Problem

Traditional reconciliation engines match rows by transaction amount and timestamp. But matching numbers alone is not financial proof. A refund matching exact net monetary value can easily belong to an entirely different payment lifecycle.

---

## The Case Ordinary Reconciliation Gets Wrong

```text
Target Payment: PAY_123
Observed Discrepancy: -₹1,500.00
Observed Refund: REF_456 (-₹1,500.00)

Accounting Identity Check : PASS
Provenance Lineage Check   : FAIL (REF_456 belongs to PAY_918)
Final Reconciliation Decision : ESCALATED
```

> **"The numbers balance. The money trail doesn't."**

---

## Architecture & Flow

```text
Financial Records (Orders, Payments, Settlements, Bank Txs)
                      │
                      ▼
             Provenance Graph
                      │
                      ▼
             Evidence Contracts
                      │
                      ▼
       Deterministic Reconciliation Gate
          /           │            \
   RECONCILED      PENDING      ESCALATED
                                    │
                                    ▼
                             AI Investigator
                            (Explanation Only)
```

The AI investigator is invoked from reconciliation orchestration to generate human-readable explanations and hypotheses, but has **no authority** over the deterministic closure gate.

---

## Judge Demo

To explore the curated 7-case interactive Judge Demo:

```bash
make test
make test-no-ai
uvicorn main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/static/index.html` and navigate through the 7 deterministic scenarios:

1. `CLEAN` -> **RECONCILED** (Clean match)
2. `SPLIT_SETTLEMENT` -> **RECONCILED** (Split settlement across batches)
3. `MISSING_FEE_EVIDENCE` -> **ESCALATED** (Fee arithmetic matches rate, but fee contract evidence is missing)
4. `ADV_SAME_AMOUNT_WRONG_TX` -> **PENDING** (Matching amount found in context, but provenance unproven)
5. `ADV_DUPLICATE_UTR` -> **ESCALATED** (Bank UTR duplicated across transactions)
6. `ADV_WRONG_REFUND_PERFECT_DISCREPANCY` -> **ESCALATED** (Hero Case: perfect math, wrong payment provenance)
7. `PENDING_BANK_SLA_SAFE` -> **PENDING** (Gateway settlement confirmed; bank credit within valid 24h SLA)

---

## Finance Controller Closure Policy

Every automatic closure satisfies the applicable evidence contract for the target money lifecycle.

The controller closes only when the required observed evidence for the selected lifecycle is complete and internally consistent. It does not assume that the absence of a fee record proves zero fee. Fee and tax deductions are treated as explicit lifecycle evidence when they are part of the target contract or when the settlement arithmetic requires them.

---

## AI Authority Boundaries

| AI MAY: | AI MAY NOT: |
| --- | --- |
| • Rank evidence-backed hypotheses<br>• Explain proof gaps in plain text<br>• Suggest manual investigation steps<br>• Summarize complex exceptions | • Perform authoritative accounting arithmetic<br>• Fabricate financial evidence<br>• Authorize closure (`authorize_closure` is blocked)<br>• Override temporal or contract validity<br>• Convert hypotheses into financial facts |

---

## Evaluation & Benchmarks

### Fixed Synthetic V2.1 Safety Benchmark
- **Cases:** 105 cases across 21 scenario families
- **Expected Labels:** 30 RECONCILED, 10 PENDING, 65 ESCALATED
- **Observed Unsafe Closures:** 0
- **Proof Citation Precision:** 100.0%

*Disclaimer: Observed on the fixed synthetic V2.1 benchmark. This does not establish production accuracy. See [Benchmark Methodology](docs/BENCHMARK_METHODOLOGY.md) for details.*

### Scale Benchmark
- **Scale:** 2,500 cases / 20,079 records
- **Total Measured Runtime:** ~0.27s
- **Throughput:** ~9,430 cases/sec
- **Latency (per case):** p50 ~0.09ms, p95 ~0.13ms

*Disclaimer: Target subgraph extraction + reconciliation, sequentially. Full graph construction excluded from reconciliation latency.*

---

## Reproduce Clean-Clone Evaluation

```bash
make test
make test-no-ai
make eval
make eval-scale
```

---

## Red-Team Hostile Discoveries

See [Hostile Failure Log](docs/FAILURE_LOG.md) for details on how adversarial red-teaming uncovered shared-settlement graph contamination, duplicate UTR bypasses, and wrong-refund math matches, leading to hardened regression tests.

---

## Limitations

- Synthetic financial datasets
- Single-currency scope (No FX conversion)
- No live production merchant gateway API integration
- Strict temporal ordering may flag delayed distributed events
