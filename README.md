# Finance Controller

## Don't match transactions. Prove what happened to the money.

Traditional reconciliation asks: "Which records match?"
Naive AI reconciliation asks: "What probably happened?"
This Finance Controller asks: **"What happened to the money, and does the available evidence constitute sufficient proof to safely close the books?"**

It replaces probabilistic matching with a Proof-Carrying Financial Provenance Engine.

### Final Evaluated Metrics (v1.0)
- **Adversarial Safety**: 0 unsafe closures across 36 adversarial boundary cases.
- **Complex Operations F1**: 0.7436 across 150 synthetic structures (1144 records).
- **Proof-Complete Closure**: 100% (The system refuses to close without a continuous subgraph of financial evidence).
- **Proof Debt Tracking**: Actively measures gross unverified ledger exposure in real-time.

---

### 30-Second Example

**Case A: The Happy Path**
A ₹1,000 order has a payment, a 2% fee, 18% tax, and a ₹976.40 settlement. The AI traverses the complete lifecycle, proves the accounting identity exactly, and safely marks the ledger as `RECONCILED`.

**Case B: The Plausible Counterfactual**
A ₹1,000 order has a payment and a ₹976.40 settlement. **However, the fee and tax records are missing.**
A probabilistic system might auto-close this because "976.40 is obviously the standard deduction."
This Controller constructs the exact same hypothesis ("Missing Fee"), flags it as a mathematically plausible **counterfactual**, warns that evidence is missing, and halts automation (`ESCALATED`).

**Plausibility != Proof.**

---

## Architecture

The system consists of three main components:
1. **Provenance Graph (NetworkX)**: Models the actual lifecycle of money as a directed graph rather than tabular rows.
2. **Reconciliation Engine (Deterministic)**: Evaluates subgraphs against strict, evidence-based Proof Contracts.
3. **AI Investigator (Offline Fallback)**: Examines broken subgraphs to generate testable counterfactual hypotheses for human reviewers.

---

## Quickstart

```bash
# Clone the repository
git clone <repo-url>
cd finance

# Install dependencies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start the application
uvicorn main:app --host 127.0.0.1 --port 8000
```
Open `http://localhost:8000` in your browser.

## Docker

```bash
docker build -t finance-controller .
docker run -p 8000:8000 finance-controller
```

## Tests

Execute the complete regression and isolation suite:
```bash
pytest test_system.py
```

## Limitations

- **Synthetic Evaluation**: All data is synthetically generated.
- **Benchmark Size**: The Complex Finance Close benchmark contains 150 cases and 1144 records. While structurally rich, it is not production-scale volume.
- **No Live Merchant Credentials**: The Razorpay adapter simulates compatibility. No live API credentials or real PII are used.
- **Offline Fallback Investigator**: The current AI investigator uses rules-based offline counterfactuals to ensure safety and determinism during the hackathon demo environment without relying on external LLM availability.
- **No FX Modeling**: Currency mismatch is supported as an adversarial failure mode, but explicit FX conversion math is not modeled.
