# Finance Controller

## Don't match transactions. Prove what happened to the money.

Finance Controller is a proof-carrying reconciliation agent that reconstructs financial provenance across payments, fees, refunds, settlements, and bank transactions.

Deterministic accounting verifies what can be proven. A bounded investigator examines broken evidence chains without being allowed to manufacture missing evidence.

Every automated closure can carry a Reconciliation Proof. Unresolved financial value becomes visible as Proof Debt.

**36 synthetic adversarial cases**  
**₹989,416 evaluated**  
**0 observed unsafe closures**  
*(Note: These metrics belong strictly to the synthetic adversarial evaluation)*

---

## WHY THIS EXISTS

Traditional reconciliation asks: "Which records match?"
Naive AI reconciliation asks: "What probably happened?"
Finance Controller asks: "What happened to the money, and is there sufficient evidence to safely automate closure?"

AI makes explanations cheap. Financial automation needs verification.
Finance Controller doesn't automate reconciliation by guessing better. It automates only the cases it can prove.

## 30-SECOND EXAMPLE

**CASE A:**
Numbers reconcile → Provenance complete → Proof Contract satisfied
Result: Automated closure + Reconciliation Proof

**CASE B:**
Numbers mathematically reconcile → Missing fee evidence → Counterfactual explanation exists → Proof Contract incomplete
Result: Auto-closure blocked → Proof Gap → Human review

*Finance Controller separates what is plausible from what is proven.*

## HOW PROOF-CARRYING RECONCILIATION WORKS

### 1. MONEY TRAIL
A Financial Provenance Graph traces the complete lifecycle of money.

### 2. PROOF CONTRACTS
Decimal-level deterministic rules check for Temporal Validity, Accounting Identity, and Evidence Conflicts.

### 3. PROOF DEBT
Unresolved financial value becomes visible as Proof Debt. It represents financial value whose lifecycle cannot currently be fully verified, not realized financial loss.

## EVALUATION

- **Adversarial Resilience:** No unsafe closures were observed across 36 synthetic adversarial cases designed to test numeric coincidence, incorrect provenance, duplicate identifiers, conflicting evidence, and ambiguous relationships.
- **Evidence Degradation:** In testing, as evidence retention dropped from 100% to 0%, the unsafe closure rate remained identically bound at 0.0%, safely abstaining up to 100.0% of the time. Less evidence → Less autonomy.

## ARCHITECTURE

FINANCIAL RECORDS
↓ 
MONEY TRAIL (Financial Provenance Graph)
↓
ACCOUNTING CHECK (Decimal / deterministic rules)
↓
PROOF CONTRACT (Evidence + temporal validity + contradictions)
↓
IS PROOF COMPLETE?
YES → RECONCILE → RECONCILIATION PROOF
NO → BOUNDED INVESTIGATOR → HYPOTHESIS
↓
EVIDENCE FOUND?
YES → reevaluate Proof Contract
NO → ABSTAIN / HUMAN REVIEW

## QUICKSTART

1. Install dependencies: `pip install -r requirements.txt`
2. Run tests: `pytest test_system.py`
3. Launch the Backend API: `uvicorn main:app --reload`
4. Access the web interface at `http://localhost:8000` to explore the Judge Demo.

## LIMITATIONS

- Small normal held-out dataset (7 cases).
- Synthetic data only.
- Limited adversarial evaluation.
- No live merchant credentials used in benchmark.
- Offline investigator/fallback logic used.
- No native FX reconciliation without explicit FX evidence.
- Fee assumptions are currently schema-specific.
# razor-pay
