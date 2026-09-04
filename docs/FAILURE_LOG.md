# Failure Log

We treated the benchmark as something to falsify, not something to make green.

### Customer connected-component contamination
**Symptom**: Unrelated payment and settlement pairs spanning different customers were being falsely matched.
**Why it mattered**: Reconciling payments based on amount collisions without verifying provenance compromises the accounting identity.
**Root cause**: The initial provenance graph connected all entities globally without restricting paths strictly to the individual order's sub-graph.
**Fix**: Implemented strict customer sub-graph extraction, isolating evidence per order.
**Regression test**: `test_adversarial_wrong_bank_transaction_rejected` inside `test_system.py` ensuring disconnected bank transactions never match.

### Split settlement incorrectly labeled Layer 1
**Symptom**: 1:N splits were inaccurately flagged as basic exact matches.
**Why it mattered**: Masked composite multi-settlement complexity inside simpler evaluation buckets, degrading transparency.
**Root cause**: Layer logic checked absolute equality without verifying 1:1 vs 1:N cardinality.
**Fix**: Correctly routed splits to Layer 2 and checked explicit edge relations.
**Regression test**: `test_reconciliation_exact_layer` to verify Layer boundaries.

### Missing-fee mathematical-signature unsafe closure
**Symptom**: The AI investigator incorrectly authorized closures when the missing fee amount neatly covered the expected gap.
**Why it mattered**: Mathematical plausibility is not cryptographic or accounting proof. Without an explicit fee record, this is a dangerous assumption.
**Root cause**: The AI was given leeway to hypothesize and act upon mathematical fits without strict constraints on evidence types.
**Fix**: Enforced a firm evidence contract demanding explicit `Fee` nodes; AI now escalates these.
**Regression test**: `test_ai_agent_missing_fee_safety_constraint`

### Ground-truth/evaluator leakage concerns
**Symptom**: Scenario strings (e.g., `ADV`, `WRONG`) embedded in identifiers leaked into runtime decision logs.
**Why it mattered**: The reconciliation agent inadvertently used heuristics from the test harness, voiding the integrity of the benchmark.
**Root cause**: The evaluator and runtime reconciliation engine were tightly coupled in `eval_engine.py`.
**Fix**: Evaluator logic entirely decoupled and moved to `evaluation/policy.py` and `evaluation/metrics.py`.
**Regression test**: `test_metric_wiring` and manual audit demonstrating zero `ADV` leakage in runtime endpoints.

### Proof Debt aggregation mismatch
**Symptom**: The overall financial exposure exceeded the sum of individual Proof Debt categories.
**Why it mattered**: Financial reporting must maintain strict accounting identity. 
**Root cause**: `PENDING` cases were inconsistently bundled with `MISSING_EVIDENCE` inside the legacy evaluation partitions.
**Fix**: Separated `PENDING_WITHIN_SLA` from `Actionable Proof Debt` in `close_the_books_partition`.
**Regression test**: `test_close_the_books_partition` verifying exactly category sum == total exposure.

### Binary policy metric semantics problem
**Symptom**: The policy evaluation returned confusing macro F1 numbers.
**Why it mattered**: Precision on "Pending" wasn't appropriately factored against "Reconciled" and "Escalated", warping automation limits.
**Root cause**: Evaluation used a 2-class binary model instead of accounting for 3 distinct states.
**Fix**: Added a strict 3-state policy matrix calculation with explicit `safe_closure_recall` and `unsafe_closure_rate`.
**Regression test**: `test_policy_evaluation_v2`

### Timestamp jitter vs evaluation-clock bug
**Symptom**: Deterministic tests failed sporadically depending on the exact run-time.
**Why it mattered**: Financial systems must compute SLA and latency windows deterministically, regardless of execution time.
**Root cause**: The system evaluated temporal gaps using `datetime.now()` globally.
**Fix**: Implemented `as_of_time` into the explicit evaluation context for the benchmark.
**Regression test**: `test_clock_leakage_regression` and strict SLA boundary negative controls.

### abs(delta) temporal-direction bug
**Symptom**: Settlement times strictly in the future were treated as valid if they were close enough to the evaluation date.
**Why it mattered**: Time travel invalidates causal order constraints.
**Root cause**: Delta calculation used absolute values, negating temporal directionality.
**Fix**: Checked if delta < 0 and threw a `FUTURE_DATED_EVIDENCE` exception.
**Regression test**: `test_temporal_negative_controls` (Sub-test D).

### Case-ID-derived timestamp bug
**Symptom**: Some adversarial datasets failed because generated timestamps drifted uncontrollably over iterations.
**Why it mattered**: Time gaps for SLA checking became unpredictable in the complex datasets.
**Root cause**: The data generator incorrectly chained timestamp increments across all generated batches.
**Fix**: Pinned the generation baseline to a strict `base_time` for all synthetic records.
**Regression test**: `test_stratified_scenario_distribution`

### Global benchmark clock leakage concern
**Symptom**: Following an evaluation pass, API endpoints could exhibit broken clock logic.
**Why it mattered**: The benchmark clock state bled into the core reconciliation service.
**Root cause**: The `engine.evaluation_time` was mutated globally during benchmarking.
**Fix**: Shifted to passing `as_of_time` as a localized request-scoped argument instead of globally.
**Regression test**: `test_clock_leakage_regression`
