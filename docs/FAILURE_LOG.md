# Failure Log

This document records the major discoveries from the hostile-audit and red-team testing phases, explaining the findings, their potential dangers, observed behaviors, the applied fixes, and references to their regression tests.

## 1. Shared-Settlement Graph Contamination
* **Finding**: `get_subgraph_for_order` aggressively pulled in all orders sharing a single settlement without properly distinguishing between target evidence and contextual evidence.
* **Why dangerous**: Could lead to "Customer Contamination" where the AI investigated an order but saw another user's completely unrelated payment details.
* **Observed behavior**: `ADV_CUSTOMER_COMPONENT_CONTAMINATION` falsely evaluated to `RECONCILED` because it had a valid settlement.
* **Fix**: Restructured `get_subgraph_for_order` to explicitly mark `is_target_evidence = True` or `False`. Non-target edges are restricted to settlement items and bank transactions for balancing, ignoring peer customer nodes.
* **Regression test**: `tests/test_graph_contamination.py`

## 2. Missing-Bank Validity Bypass
* **Finding**: Missing evidence (e.g. absent BankTransaction) triggered `PENDING_SETTLEMENT` SLA logic but mistakenly flagged the evidence contract as complete.
* **Why dangerous**: Bypassed strict proof requirements and incorrectly yielded 1.0 Proof Completeness score despite missing records.
* **Observed behavior**: Missing bank transactions allowed closures to proceed without alerting human reviewers of incomplete proof.
* **Fix**: Implemented `evidence_slots` that strictly track whether *found* candidates satisfy required types. Missing evidence yields `< 1.0` completeness.
* **Regression test**: `tests/test_redteam_p0_2.py`

## 3. AI String-Based Closure Authority
* **Finding**: The AI Investigator could directly dictate the central `final_decision` by emitting strings like `RECONCILED` or `ESCALATED`.
* **Why dangerous**: Subjected financial decisions to LLM hallucinations and prompt injection.
* **Observed behavior**: Allowed contradictory states to bypass deterministic rules if the AI provided a plausible-sounding justification.
* **Fix**: AI is now restricted strictly to an investigative role. It outputs hypothesis and suggested actions. The `authorize_closure` deterministic gate holds exclusive authority over `closure_authorized`.
* **Regression test**: `tests/test_redteam_p0_2.py`

## 4. Wrong-Reference Temporal/Provenance Bypass
* **Finding**: The temporal SLA logic allowed out-of-bounds missing evidence (e.g., beyond the SLA window) to remain PENDING if the reference was wrong.
* **Why dangerous**: A bank transaction that is blatantly wrong but outside SLA could be mistakenly deferred rather than immediately escalated.
* **Observed behavior**: Delayed failures.
* **Fix**: `temporal_valid` and strict matching enforces that only perfectly aligned target proof passes, else escalates.
* **Regression test**: `tests/test_exception_precedence.py`

## 5. Fabricated Scale Percentiles
* **Finding**: Legacy output reported latency as hardcoded or statistically meaningless averages.
* **Why dangerous**: Presented a false sense of production-readiness.
* **Observed behavior**: Benchmarks emitted `p95` based on tiny synthetic sets or hardcoded constants.
* **Fix**: Rebuilt `run_scale.py` to correctly log and compute actual measured times across specifically defined boundaries.
* **Regression test**: `evaluation/run_scale.py`

## 6. Refund Double-Counting
* **Finding**: Gross/Net settlement checks allowed overlapping refunds or double deductions.
* **Why dangerous**: Allowed incorrect arithmetic balances to inadvertently appear perfect.
* **Observed behavior**: Incorrect arithmetic closed successfully.
* **Fix**: Unitemized refunds are explicitly tracked globally across the target's subgraph via `unitemized_refunds`, verified to exactly equal the internal discrepancy of `s.amount` vs `s_items_total`.
* **Regression test**: `tests/test_redteam_accounting.py`

## 7. Type-Based Rather Than Instance-Sensitive Proof Completeness
* **Finding**: `proof_completeness` checked `if "BankTransaction" in found_types` rather than whether the *specific* bank transaction was validly matched.
* **Why dangerous**: An invalid, wrong-reference bank transaction could still satisfy the contract slot.
* **Observed behavior**: `ADV_WRONG_TAX_PERFECT_SIGNATURE` etc. resulted in 1.0 proof completeness.
* **Fix**: Implemented strict `evidence_slots`. A candidate must explicitly satisfy amount/reference/provenance matching to fill its instance-sensitive slot.
* **Regression test**: `tests/test_redteam_p0_2.py`

## 8. Duplicate UTR Unsafe Closure
* **Finding**: 1:N hijacking of bank contexts. A valid bank transaction could satisfy the contract even if it was double-spent across multiple unrelated settlements.
* **Why dangerous**: Could allow multiple discrepancies to mask themselves behind a single UTR.
* **Observed behavior**: `ADV_DUPLICATE_UTR` resulted in `PENDING` instead of `ESCALATED`.
* **Fix**: Enforced `len(linked_settlements) <= 1` for each bank transaction. Any duplication sets `contradiction_valid = False` with `DUPLICATE_UTR`.
* **Regression test**: `tests/test_redteam_p0_2.py::test_duplicate_utr_unsafe_closure`

## 9. Wrong-Refund-Perfect-Arithmetic Unsafe Closure
* **Finding**: Unitemized refunds belonging to the wrong payment globally subtracted from the target subgraph's accounting perfectly without verifying exact target order relationship.
* **Why dangerous**: Arithmetic equality downgraded a provenance conflict (the settlement amount didn't balance internally) to a `PENDING` missing-bank state.
* **Observed behavior**: `ADV_WRONG_REFUND_PERFECT_DISCREPANCY` evaluated to `PENDING`.
* **Fix**: Promoted internal settlement balancing (`s.amount` != sum of internal items) to a strict hard contradiction `WRONG_REFUND_PROVENANCE` unless perfectly offset by globally-linked refunds inside the target subgraph.
* **Regression test**: `tests/test_redteam_p0_2.py::test_wrong_refund_perfect_arithmetic`

## 10. Malformed Timestamp-Lure Benchmark Scenario
* **Finding**: The `ADV_TIMESTAMP_LURE` datagen incorrectly timestamped the required, primary target BankTransaction +60 days into the future while expecting `RECONCILED`.
* **Why dangerous**: The benchmark required the engine to ignore its own temporal policy and accept impossible future evidence to pass.
* **Observed behavior**: The engine rightfully marked it `ESCALATED`.
* **Fix**: Corrected the scenario generator to emit a valid target bank record and a separate, completely unrelated future-dated lure record.
* **Regression test**: `evaluation/run_v2_1.py`
