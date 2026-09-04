# Final Evaluation V2.1

**Benchmark Version:** COMPLEX_BENCHMARK_V2_1
**Seed:** 4242
**Case Count:** 105
**Record Count:** 835
**Scenario/Mechanism Count:** 21
**Total Exposure:** ₹2383358.52

## Financial Partition
- **PROVEN:** ₹702367.95
- **PENDING:** ₹131814.04
- **Actionable Proof Debt:** ₹1549176.53

## Three-State Policy Matrix
```json
{
  "RECONCILED": {
    "RECONCILED": 25,
    "PENDING": 0,
    "ESCALATED": 5
  },
  "PENDING": {
    "RECONCILED": 0,
    "PENDING": 10,
    "ESCALATED": 0
  },
  "ESCALATED": {
    "RECONCILED": 10,
    "PENDING": 0,
    "ESCALATED": 55
  }
}
```

## Policy Accuracy Metrics (observed on the fixed synthetic V2.1 benchmark)
- **Observed Unsafe Closure Rate:** 0.1538
- **Safe Closure Recall:** 0.8333
- **Pending-State Accuracy:** 1.0000
- **Exception Detection Recall:** 0.8462
