# Final Evaluation V2.1

**Benchmark Version:** COMPLEX_BENCHMARK_V2_1
**Seed:** 4242
**Case Count:** 105
**Record Count:** 840
**Scenario/Mechanism Count:** 21
**Total Exposure:** ₹2401766.15

## Financial Partition
- **PROVEN:** ₹634385.16
- **PENDING:** ₹0.00
- **Actionable Proof Debt:** ₹1767380.99

## Three-State Policy Matrix
```json
{
  "RECONCILED": {
    "RECONCILED": 30,
    "PENDING": 0,
    "ESCALATED": 0
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
- **Safe Closure Recall:** 1.0000
- **Pending-State Accuracy:** 1.0000
- **Exception Detection Recall:** 1.0000
