# Architecture

Sources / Adapters
        |
        v
Canonical Financial Records
        |
        v
Financial Provenance Graph
        |
        v
Deterministic Reconciliation Engine
        |
        +--> Proof Contract
        +--> Accounting Identity
        +--> Temporal Validity
        +--> Contradiction Guard
        |
        v
Closure Gate
   |            |
PROVEN       NOT PROVEN
   |            |
Close      AI Investigator
               |
               v
        Evidence-backed hypotheses
               |
               v
        Human / operational action

### The Role of AI
The AI Investigator operates entirely strictly off the accounting authority path. It acts solely as an analytical layer over unresolved and escalated cases. It is empowered to generate explanations and draft action plans, but it cannot authorize closures, rewrite evidence, override temporal constraints, or dictate truth to the financial logic engine.
