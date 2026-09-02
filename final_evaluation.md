# Final Evaluation Results

Generated at: 2026-09-02T09:50:48.688315

## Datasets
- **NORMAL_HELD_OUT**: 7 cases, 56 records
- **ADVERSARIAL**: 36 cases, 270 records
- **COMPLEX_FINANCE_CLOSE**: 150 cases, 1144 records (Value: ₹3805702.00)

## Complex Finance Close Benchmark
| Metric | Exact | Rules | Controller |
|--------|-------|-------|------------|
| Decision F1 | 0.7436 | 0.7436 | 0.7436 |
| Safe Auto-closure | 0.8417 | 0.8417 | 0.8417 |
| Unsafe Closure | 0.0000 | 0.0000 | 0.0000 |

## Close The Books Workflow
- **Batch Size**: 150 cases
- **Value**: ₹3805702.00
- **Proven Value**: ₹578341.55
- **Proof Debt**: ₹3227360.45
- **Exceptions**: 75
- **Automation Rate**: 19.3%
