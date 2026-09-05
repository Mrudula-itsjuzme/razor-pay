# Finance Controller Architecture

## 1. System Pipeline

```
Input Financial Records (Orders, Payments, Refunds, Fees, Taxes, Settlements, Bank Transactions)
                                   |
                                   v
                     Provenance Graph Construction
                                   |
                                   v
          Target Subgraph Extraction (`get_subgraph_for_order`)
                                   |
                                   v
       Candidate / Composite Settlement Reconciliation & Balancing
                                   |
                                   v
          Evidence Contract Slot Matching (`evidence_slots`)
                                   |
                                   v
             Deterministic Closure Gate (`authorize_closure`)
                                   |
           +-----------------------+-----------------------+
           | (All Valid)           | (Missing inside SLA)   | (Contradiction / Invalid)
           v                       v                       v
      RECONCILED                PENDING                ESCALATED
(DETERMINISTIC)       (TEMPORAL_DETERMINISTIC)  (HUMAN_REVIEW_REQUIRED)
                                                           |
                                                           v
                                                     AI Investigator
                                                (Explanation & Hypothesis Only)
```

## 2. Deterministic Authority Boundary
The single authoritative entrypoint for financial closure is `ReconciliationEngine.authorize_closure(...)`.

Closure requires boolean `True` across all 7 deterministic gates:
1. **`accounting_valid`**: Expected net balances observed settlement net.
2. **`evidence_contract_valid`**: Required slot types exist for the contract.
3. **`provenance_valid`**: Evidence is linked directly along target provenance edges.
4. **`temporal_valid`**: Timestamps are valid relative to `as_of_time` and sequence.
5. **`contradiction_valid`**: No observed contradictions (e.g. duplicate UTRs, unexplained discrepancies).
6. **`currency_valid`**: Currencies match expected ISO codes.
7. **`proof_complete`**: Instance-sensitive proof slot completeness equals 1.0.

If any single gate evaluates to `False`, `authorize_closure()` returns `False`. The system strictly prohibits auto-closure.

## 3. Evidence / Provenance Model
Rather than performing loose arithmetic or fuzzy string matching across raw flat tables, the controller models financial lifecycles as a directed acyclic graph $G=(V, E)$. Nodes represent typed domain entities (`Order`, `Payment`, `Fee`, `Tax`, `Refund`, `Settlement`, `BankTransaction`). Edges represent explicit money flow semantics (`GENERATED`, `INCURRED`, `INCLUDED_IN`, `CREDITED_AS`).

### Full-Lifecycle Evidence Contracts
The contract is not purely amount-based. When a payment lifecycle includes a fee, tax, or a settlement arithmetic adjustment implied by the net difference, the engine upgrades to a `FULL_LIFECYCLE` contract. In that mode, the required proof set can include `Fee` and/or `Tax` as explicit evidence slots. A missing fee record is not treated as a zero-fee claim; it is treated as a proof gap until the supporting evidence is observed.

## 4. Target Evidence vs. Settlement Context
When isolating an order for reconciliation, `get_subgraph_for_order` labels nodes with an `is_target_evidence` flag. Subgraph traversal retains sibling settlement items and bank credits strictly for balance verification while blocking peer customer orders from contaminating the target proof context.

## 5. AI Boundary
The AI Investigator (`ai_agent.py`) is strictly sandboxed.
- **Allowed**: Generating hypotheses, summarizing missing evidence, suggesting next investigation steps for human reviewers.
- **Forbidden**: Outputting `RECONCILED`, overriding accounting balance, setting `closure_authorized`, or altering evidence completeness metrics.

When LLM credentials are absent or the model API fails, the system falls back seamlessly to `OfflineFallbackInvestigator` or returns a default manual review recommendation. The deterministic reconciliation gate functions identically with or without AI.

## 6. State Semantics
- **`RECONCILED`**: All required proof is valid and closure is authorized by the deterministic gate.
- **`PENDING`**: Required evidence is missing, but no contradiction is observed, and the lifecycle remains strictly within the configured SLA window. This applies to the `PENDING_SETTLEMENT` contract, where the bank transaction is not yet present but still within the temporal allowance.
- **`ESCALATED`**: Contradictory, invalid, provenance-conflicting, temporally impossible evidence is observed, or evidence remains missing beyond SLA. In full-lifecycle cases, missing fee/tax proof for an implied deduction is escalated rather than silently treated as zero-fee.

## 7. Benchmark Architecture
- **V2.1 Fixed Benchmark**: 105 cases across 21 adversarial/clean scenario families under fixed seed and static evaluation time.
- **Scale Benchmark**: 2,500 cases / 20,079 records measuring target extraction and reconciliation throughput independently of full graph ingestion.

## 8. Explicit Trust Boundaries
- **Synthetic Data**: Benchmarks operate on synthetic data schemas.
- **Scope**: Results reflect performance on the fixed synthetic evaluation suite and do not claim universal production accuracy.
