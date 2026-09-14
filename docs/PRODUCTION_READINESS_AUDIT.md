# Backend production readiness audit

Date: 2026-09-06. Checkout: main, commit `182c597`. Verdict: **NOT READY for production financial data or authoritative closure**.

Scope: FastAPI backend, canonical models, provenance graph, reconciliation gate, gateway adapter, evaluation logic, dependency and container configuration. This is a local code and synthetic execution audit; no deployed environment, real merchant records, gateway credentials, database recovery, container build or external perimeter was validated. Application source was not modified.

## Verified checks

- Existing tests: **99 passed, 2 deselected, 1 deprecation warning** in 1.29 seconds using the existing venv, cleared inherited PYTHONPATH and disabled pytest plugin autoload. Full run timed out after 90 seconds in expensive dataset fingerprint checks; the two dataset signature tests remain unverified. Initial sandbox test runs were interrupted after stalling.
- `env -u PYTHONPATH venv/bin/python -m pip check`: PASS. Inherited ROS paths polluted the first check; clearing PYTHONPATH removed those unrelated failures. This is dependency consistency, not a vulnerability scan.
- Fresh fixed synthetic V2.1 benchmark: 105 cases / 840 records; 30 reconciled, 10 pending, 65 escalated; zero unsafe closures on those benchmark scenarios. This does not cover the invalid inputs reproduced below.
- Fresh sequential scale benchmark: 2,500 cases / 20,079 records; graph construction 10.43 seconds; extraction plus reconciliation 0.400 seconds, about 6,257 cases/second, p95 0.219 ms. These are in-process synthetic timings, not API load or multiworker results.
- Additional local probes reproduced all failures below without live gateway calls. Evidence: [probe script](production-audit/probes.py), [benchmark](production-audit/benchmark.json), [scale run](production-audit/scale.json).

## Critical correctness blockers

### 1. Invalid bank and settlement evidence can authorize closure

`reconciliation.py:184-201` sums bank amounts without checking `direction`; `reconciliation.py:259-265` accepts settlements without checking status. A clean 100 INR lifecycle remains `RECONCILED`, `proof_validity=PASS` after changing the bank transaction to DEBIT. Independently, setting settlement status to FAILED also returns the same successful closure.

Required: validate authoritative lifecycle states and bank direction before counting evidence. Invalid states must block closure and produce an explicit conflict. Cover both failures with regression tests.

### 2. Tax currency and future adjustment evidence bypass the gate

`reconciliation.py:371-379` omits taxes from currency validation. Temporal checks at `reconciliation.py:112-151` do not reject future tax or refund creation timestamps. Probes each independently receive `RECONCILED` and `PASS` with (a) a USD tax deducted from an INR lifecycle, (b) a tax created 100 days later, or (c) a processed refund created 100 days later than the underlying payment, evaluated only five days after payment.

Required: validate currency and as-of availability for every contributing record, including tax, refund, fee, and settlement completion evidence. Preserve explicit time semantics for historical replay.

## High priority backend blockers

### 3. No application authentication, authorization, tenant isolation or durable storage

`main.py:16-22` enables wildcard CORS; API routes have no authentication dependencies. Anonymous POST `/api/demo` returns 200. Demo and ingestion replace shared process globals (`main.py:30-32,49,99`); degradation endpoints alter shared decisions. There is no merchant identity in the data model, database, immutable evidence store, persisted decision history, transactional replacement, or concurrency control.

Impact: any caller reaching the service can read available records or replace the dataset; restart loses data; worker processes hold independent states; concurrent load and reads can observe partial replacement. No external auth proxy was inspected, so application exposure is distinguished from any unknown deployment perimeter.

Required: tenant-scoped authorization and storage, durable versioned evidence and decisions, atomic ingestion, replay/conflict handling, and production exclusion of demo/destructive evaluation routes.

### 4. Ingestion does not ingest live financial lifecycles and is unbounded

`main.py:97-106` fetches adapter output but discards `rzp_records` and always calls `generate_dataset(num_orders)`. The adapter only maps orders, has no pagination or payment/refund/settlement implementation (`razorpay_adapter.py:32-45`), and its SDK is absent from requirements and Docker installation.

The local probe POST `/api/ingest?num_orders=-1` returns 200 and leaves zero cases, replacing a populated dataset. The parameter has no upper bound; ingestion performs nested graph-linking scans, and expensive benchmark/evaluation routes are synchronous with no admission limits.

Required: separate explicit demo mode from production, reject invalid configuration instead of silently selecting synthetic data, implement complete source ingestion, validate bounded request sizes before mutation, stage updates atomically, and move large jobs into controlled background processing.

### 5. Timezone-qualified timestamps produce HTTP 500

GET `/api/reconcile/{clean_order}?as_of_time=2026-09-06T12:00:00Z` returns 500. Pydantic accepts the timezone-aware timestamp; the engine compares it with naive source datetimes and `datetime.now()` (`reconciliation.py:29,114`). Adapter timestamps also use naive `datetime.fromtimestamp`.

Required: one timezone-aware UTC representation throughout ingestion and evaluation, explicit legacy timestamp conversion, and validation errors for unsupported inputs rather than runtime exceptions.

### 6. Detail, list and batch use different evidence state

Degrade a CLEAN demo case: the detail returns ESCALATED while `/api/cases` still returns RECONCILED. `main.py:147-151` applies degradation only to detail (and graph); list at `main.py:161-162` and batch at `main.py:300-302` reconcile the original graph. Reloading the demo leaves the old degradation flag in place.

Required: centralize effective evidence selection for every consumer and reset demo-only state atomically. Remove artificial degradation capabilities from production.

## Further business logic and provenance gaps

- **Pending money is misclassified:** the fresh benchmark's decision matrix contains 10 PENDING cases, but its financial partition reports zero pending cases and zero pending exposure. `evaluation/policy.py:263-290` expects `exception_details.exception_type=PENDING_EVIDENCE`, while the engine's normal PENDING result does not contain exception details. These cases fall into UNCLASSIFIED and actionable debt. Classify by the actual decision before exception metadata; reconcile counts and monetary partitions in tests.
- **Order amount is not part of accounting validation:** changing the order amount from 100 to 1,000 while leaving the captured/settled/banked value at 100 still closes with PASS. `reconciliation.py:86-111` starts from captured payments. If partial payments are supported, distinguish payment-level reconciliation from full-order closure; otherwise enforce order/capture conservation. The business contract needs an explicit decision here.
- **Graph imports lose evidence identity:** `graph.py:52-59` represents settlement items as a single DiGraph edge per source/destination, dropping item ID, currency and declared settlement ID. Repeated same-pair items overwrite instead of preserving distinct evidence; node reimports also replace data without a conflicting-payload check. Preserve source IDs, import versions and idempotency/conflict semantics.
- **Canonical schemas accept unconstrained monetary values and arbitrary statuses:** `models.py` lacks sign, scale and lifecycle state constraints. Validate each record type's contract before graph insertion, including refund/payment amounts and currency precision.
- **Reporting is not an operational audit:** `/api/eval_lab` returns literal PASS values for leakage and replay without performing those checks (`main.py:272-273`). `/api/batch` unsafe-closure counting recognizes only two ground-truth categories. These outputs should not be production safety attestations.

## Deployment and operational gaps

Dockerfile installs an unpinned subset of dependencies instead of a locked application manifest, uses root, and copies the whole directory without a `.dockerignore` (including any local `.env`, venv and repository metadata present in the build context). Requirements are also unpinned. The app has no production configuration gate, health/readiness endpoint checking dependencies, structured decision audit persistence, or checked-in CI pipeline. No backup/restore, migration, retention, rollback, rate limiting or load-test evidence was found in this checkout.

Required: reproducible minimal container with a non-root user and explicit context exclusions; validated startup configuration; health/readiness and operational telemetry; a CI gate that includes the new adversarial cases; then staging validation of authenticated ingestion, replay, concurrent requests, restarts, worker consistency and restore.

## Reproduce

Run from the repository root; the probes modify only isolated in-process synthetic state and mock the adapter fetch.

```sh
env -u PYTHONPATH PYTHONPATH=. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 venv/bin/python -m pytest -q -k 'not test_v2_1_dataset_is_deterministic_with_fixed_seed and not test_v2_1_seed_changes_generated_case_values'
env -u PYTHONPATH PYTHONPATH=. venv/bin/python docs/production-audit/probes.py
env -u PYTHONPATH venv/bin/python -m pip check
```

Priority: first block unsafe closures and unauthenticated production exposure; next implement durable, tenant-scoped real ingestion and consistent time/evidence semantics; finally validate the deployment and recovery path. Passing the current benchmark alone is insufficient for release.
