# Finance Controller

**A proof-carrying reconciliation agent for payment operations.**

Reconstructs what happened to the money, automatically closes only what the evidence proves, and turns everything else into an actionable proof gap.

> Don't match transactions. Prove what happened to the money.

## 1. THE PROBLEM
Amounts matching does not prove they represent the same money.

## 2. THE CORE IDEA
Every automated close must carry a reconciliation proof.

## 3. 30-SECOND EXAMPLE
- **Complete evidence** -> RECONCILED
- **Same arithmetic with missing fee** -> ESCALATED
- **Same-amount wrong UTR** -> ignored as unrelated evidence

## 4. CURRENT EVALUATION
**Observed on the fixed synthetic V2.1 benchmark**
- **Benchmark Version:** COMPLEX_BENCHMARK_V2_1
- **Seed:** 4242
- **Case Count:** 105
- **Record Count:** 835
- **Scenario/Mechanism Count:** 21
- **Total Exposure:** ₹2,689,785.86
- **PROVEN:** ₹579,893.71
- **PENDING:** ₹288,922.63
- **Actionable Proof Debt:** ₹1,820,969.52

**Three-State Policy Matrix (RECONCILED, PENDING, ESCALATED):**
- **Observed Unsafe Closure Rate:** 0.0%
- **Safe Closure Recall:** 83.33%
- **Pending-State Accuracy:** 100%
- **Exception Detection Recall:** 100%

## 5. PRODUCT LOOP
Close -> Investigate -> Resolve -> Prove

## 6. WHAT AI DOES / DOES NOT DO

| AI MAY: | AI MAY NOT: |
| --- | --- |
| - rank evidence-backed hypotheses<br>- explain proof gaps<br>- suggest investigation steps<br>- summarize exceptions | - perform authoritative accounting arithmetic<br>- fabricate evidence<br>- authorize closure<br>- override temporal validity<br>- override proof contracts<br>- convert hypotheses into facts |

The model may improve investigation quality. It does not determine accounting truth.

## 7. WHAT IS REAL / SIMULATED

**REAL:**
- provenance graph
- deterministic reconciliation
- proof contracts
- temporal validity
- typed exceptions
- proof certificates
- benchmark engine
- evidence degradation
- dashboard/demo

**SYNTHETIC:**
- benchmark transaction data

**RAZORPAY:**
Currently uses synthetic data generator that maps to Razorpay schemas. No live integration is demonstrated.

## 8. QUICKSTART
```bash
git clone https://github.com/Mrudula-itsjuzme/razor-pay.git
cd razor-pay
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pytest -q
python evaluation/run_v2_1.py
make demo
```

## 9. LIMITATIONS
- synthetic financial data
- no FX conversion
- no production merchant validation
- strict temporal ordering may over-flag delayed distributed events
- offline/rules fallback investigator if applicable
- benchmark scope
