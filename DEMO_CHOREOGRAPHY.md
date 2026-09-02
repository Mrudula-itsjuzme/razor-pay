# Judge Demo Choreography

## 0. Landing / Thesis
- **Action:** Open application to Judge Demo (Ops) tab.
- **State:** Clean initial load.
- **Narrative:** "Don't match transactions. Prove what happened to the money."

## 1. Split Settlement Investigation
- **Action:** Click "ORD_3000" (Split Settlement).
- **State:** Progressive reveal in the Money Trail (Order -> Payment -> Fee/Tax -> Settlement -> Bank).
- **Narrative:** "Follow the money. AI correctly traverses a 1:N split settlement and verifies the accounting identity."

## 2. Reconciliation Proof
- **Action:** Point out "Evidence Conflict Guard: PASS" and "Decision: RECONCILED".
- **State:** Proof Completeness is 1.0.

## 3. Remove Evidence
- **Action:** Click "SIMULATE MISSING EVIDENCE".
- **State:** Bank and Fee nodes vanish from the graph.
- **Narrative:** "Break the proof to test safety."

## 4. Automatic Closure Revoked
- **Action:** Observe "PROOF GAP".
- **State:** Decision becomes "ESCALATED". System refuses to close.

## 5. Restore Evidence
- **Action:** Click "RESTORE EVIDENCE".
- **State:** Nodes return, system auto-heals and closes successfully.

## 6. Missing Fee (Plausible != Proven)
- **Action:** Click "ORD_6000" (Missing fee evidence).
- **State:** Ghost node appears.
- **Narrative:** "Plausible != Proven. The AI figures out the 2% fee is the exact missing amount, but without the physical record, it explicitly blocks automation."

## 7. Close the Books
- **Action:** Go to "Exception Command Center" tab. Click "RUN CLOSE".
- **State:** Dashboard loads the month-end synthetic batch metrics.

## 8. Proof Debt / Why Isn't Book Closed?
- **Action:** Click "WHY ISN'T THE BOOK CLOSED?".
- **State:** The Unresolved Verification Exposure panel opens.
- **Narrative:** "Real finance ops. It prioritizes the actual missing evidence across the entire batch."

## 9. Complex Benchmark
- **Action:** Go to "Eval Lab & Benchmarks" tab. Click "RUN EVAL LAB".
- **State:** Complex Finance Close Benchmark loads showing 0% Unsafe Closure for the Controller compared to Exact/Rules.

## 10. Evidence Degradation
- **Action:** Scroll down to Evidence Degradation Experiment.
- **State:** "As evidence disappears, the system safely abstains rather than making unsupported guesses."
