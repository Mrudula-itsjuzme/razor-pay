# Benchmark Methodology

## V2.1 Fixed Benchmark

The V2.1 benchmark evaluates the reconciliation engine against a rigorous, fixed, synthetic dataset to ensure deterministic safety, accuracy, and strict semantic adherence to financial policy logic.

**Configuration:**
- **Total Cases:** 105 cases
- **Scenario Families:** 21 distinct families
- **Cases per Family:** 5
- **Generation:** Fixed seed and static `as_of_time`
- **Labels:** Evaluator-private expected policy states

### Final Matrix
The final reconciliation decisions correspond precisely with the mathematical expectations of the state policy:

- **RECONCILED:** 30/30 correct
- **PENDING:** 10/10 correct
- **ESCALATED:** 65/65 correct

### Finance-Specific Safety Metrics
- **0** unsafe closures
- **0** false auto-closures
- **100%** safe closure recall
- **100%** pending accuracy
- **100%** exception recall

### Proof Metrics
- **Citation Precision:** 1.0
- **Requirement Recall:** 0.95
- **Proof-Complete Closure Rate:** 1.0
- **Broken-Proof Closure Rate:** 0.0
- **Right-Decision-Wrong-Proof Rate:** 0.0

> **Explicit Disclaimer:** These metrics represent performance on a fixed, synthetic adversarial benchmark. They strictly prove adherence to hardcoded policy semantics under hostile isolation. They are **NOT** evidence of end-to-end production accuracy in a live banking environment.

### Timestamp-Lure Correction Note
`ADV_TIMESTAMP_LURE` originally timestamped the required target bank evidence in the future while labeling the case `RECONCILED`. During hostile temporal review, this inconsistency was found. The generator was corrected so the target lifecycle remains valid while a separate unrelated future-dated transaction serves as the lure. Runtime logic and expected policy label were unchanged.
