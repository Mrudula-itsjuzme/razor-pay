# Hostile Judge Q&A

### 1. Why isn't this just fuzzy matching?
Fuzzy matching compares isolated fields (e.g. matching amounts or approximate references) between tabular rows. Equal amounts often belong to completely different money lifecycles. Finance Controller builds an explicit directed provenance graph and enforces instance-sensitive proof contracts.

### 2. Why use a graph?
Payment lifecycle events (Order -> Payment -> Fee/Tax -> Refund -> Settlement -> Bank Credit) form complex N:1 and 1:N dependency graphs. Graph traversal isolates the causal trail of target money without introducing global contamination from peer transactions.

### 3. Why use AI at all?
AI is used exclusively for exception investigation and hypothesis ranking on escalated cases. When human intervention is required, the AI Investigator explains the proof gap and suggests next verification steps.

### 4. What prevents hallucinated closure?
The AI Investigator has zero closure authority. It cannot return `RECONCILED` or set `closure_authorized=True`. Closure decisions are made exclusively by a pure deterministic boolean gate (`ReconciliationEngine.authorize_closure`).

### 5. What happens when evidence is missing?
If evidence is missing but no contradiction exists and the transaction is within the SLA window, it resolves to `PENDING`. If the SLA window has expired or evidence is incomplete outside SLA, it resolves to `ESCALATED`.

### 6. What happens when the arithmetic balances but provenance is wrong?
The numbers balance, but the money trail doesn't. If a refund belongs to a different payment lifecycle, or a fee record is missing even if the amount matches, provenance and contradiction checks fail, forcing an `ESCALATED` state.

### 7. Why should we trust your benchmark result?
We do not claim universal production accuracy. We observed 0 unsafe closures and 100% policy accuracy on a published, reproducible, fixed synthetic benchmark of 105 cases across 21 scenario families. The benchmark is accompanied by an open failure log documenting past red-team discoveries.

### 8. Did you change the benchmark after seeing failures?
During hostile review of `ADV_TIMESTAMP_LURE`, we found the original generator accidentally timestamped the *required* target bank evidence 60 days in the future while expecting `RECONCILED`. We corrected the scenario so the target evidence remains valid while an unrelated future transaction serves as the lure. Runtime logic and policy expectations were unchanged.

### 9. What is synthetic?
The benchmark datasets (orders, payments, settlements, bank transactions) are synthetically generated using fixed random seeds and static evaluation timestamps.

### 10. What is the biggest current limitation?
The system currently operates on synthetic schemas, lacks multi-currency FX conversion, and does not integrate live production merchant APIs.

### 11. How would this integrate with Razorpay?
`RazorpayAdapter` maps Razorpay entity webhooks and CSV batch settlement exports into `ProvenanceGraph` nodes, feeding into the deterministic reconciliation engine.

### 12. Why is this better than an LLM reconciliation agent?
LLMs are probabilistic and prone to hallucinations or prompt injections. By restricting the LLM to hypothesis generation and keeping accounting authority in a deterministic gate, the controller guarantees zero hallucinated auto-closures.

### 13. What happens if the LLM is offline?
Financial closure correctness is completely independent of the LLM. If the AI model fails or is offline, the deterministic engine processes closures normally, and escalated cases fall back gracefully to offline rules or manual review.

### 14. What does Proof Debt mean?
Proof Debt represents the unproven financial exposure (the total value of orders in `PENDING` or `ESCALATED` states) that cannot be safely auto-closed due to incomplete or contradictory evidence.

### 15. What would you validate next with real merchant data?
We would test edge cases involving complex multi-currency fee schedules, chargeback reversals, partial settlement windows, and bank statement reference formatting variations across diverse acquiring banks.
