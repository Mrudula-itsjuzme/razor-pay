# Final Evaluation V2.1

**Benchmark Version:** COMPLEX_BENCHMARK_V2_1
**Seed:** 4242
**Case Count:** 105
**Record Count:** 835
**Scenario/Mechanism Count:** 21
**Total Exposure:** ₹2689785.86

## Financial Partition
- **PROVEN:** ₹579893.71
- **PENDING:** ₹288922.63
- **Actionable Proof Debt:** ₹1820969.52

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
    "RECONCILED": 0,
    "PENDING": 0,
    "ESCALATED": 65
  }
}
```

## Policy Accuracy Metrics (observed on the fixed synthetic V2.1 benchmark)
- **Observed Unsafe Closure Rate:** 0.0000
- **Safe Closure Recall:** 0.8333
- **Pending-State Accuracy:** 1.0000
- **Exception Detection Recall:** 1.0000
