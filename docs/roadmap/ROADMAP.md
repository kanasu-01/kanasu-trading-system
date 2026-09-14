# Kanasu Roadmap

## Purpose

This document owns Kanasu's permanent delivery hierarchy, sequencing, dependencies and roadmap status. Product boundaries are defined in the [Product Vision](../PRODUCT_VISION.md); current active work is summarized in [Project Status](../PROJECT_STATUS.md); workflow and status rules are defined in [Governance](../governance/GOVERNANCE.md).

## Permanent hierarchy

~~~text
Version
  → Phase
      → Milestone
          → Step
              → Task
~~~

- **Version** — a coherent product release and acceptance boundary.
- **Phase** — a dependency-oriented group of milestones.
- **Milestone** — a substantial capability with exit criteria.
- **Step** — a bounded part of a milestone.
- **Task** — a concrete deliverable with evidence and closure criteria.

Hierarchy ancestry is metadata. It is not encoded into identifiers. M3.6b remains M3.6b even if its phase or target version changes.

## V1 — Research and Real-Market-Data Paper Trading

### P0 — Project Foundation

- **M0 — DONE** — Repository / foundation hygiene.
- **M1 — DONE** — Authoritative simulated portfolio accounting.
- **M2 — DONE** — Execution economics/accounting correctness.
  - **M2.1 — DONE** — Single execution-price ownership and same-bar stop causality.
  - **M2.2 — DONE** — Independent brokerage-enabled semantics.
  - **M2.3 — DONE** — Account-level net P&L contribution to drawdown manager.
  - **M2.4 — DONE** — BUY execution-price reporting consistency.

### P1 — Trusted Historical Data Foundation

- **M3 — IN_PROGRESS** — Offline / historical market-data foundation.
  - **M3.1 — DONE** — Candle finite-value validation.
  - **M3.2 — DONE** — Canonical CSV candle loader and compatibility wrapper.
  - **M3.3a — DONE** — Dataset symbol/timeframe identity propagation.
  - **M3.3b — DONE** — Dataset timezone identity metadata.
  - **M3.4 — DONE** — Candle sequence integrity.
  - **M3.5 — DONE** — Safe historical chunk composition.
  - **M3.6 — DONE** — Local historical persistence and retrieval.
    - **M3.6a — DONE** — SQLite candle persistence.
    - **M3.6b — DONE** — Coverage and missing-range planning.
    - **M3.6c — DONE** — Local-first historical retrieval service.
    - **M3.6d — DONE** — Integration and failure validation.
  - **M3.7 — IN_PROGRESS** — Historical source policy/runtime wiring.
    - **M3.7a — DONE** — Historical source policy contract.
    - **M3.7b — READY / NEXT** — Broker historical provider adapter.
    - **M3.7c — PLANNED** — Backtest/WFA runtime wiring and lazy provider construction.
    - **M3.7d — PLANNED** — Source-policy integration and failure validation.
  - **M3.8 — RESERVED** — Historical-path parity/reproducibility.

### P2 — Trusted Research Engine

- **M4 — RESERVED** — Backtest validity.
- **M5 — RESERVED** — WFA validity.

### P3 — Real-Market-Data Paper Runtime

- **M6 — RESERVED** — Live market-data foundation.
- **M7 — RESERVED** — Paper-session integration.

### P4 — Research and Paper Application

- **M8 — RESERVED** — Research and paper application.

### P5 — V1 Acceptance and Release

- **M9 — RESERVED** — V1 validation and release.

M3.8 and M4–M9 are reserved proposals until formally baselined. Reservation prevents accidental identifier collision; it does not claim accepted detailed scope or authorization to implement. M3.7a is complete. M3.7b is READY / NEXT after this baseline is reviewed and committed; implementation is not authorized automatically and requires separate explicit authorization.

## Near-term detailed work

### M3.6b — Coverage and missing-range planning

**Outcome:** Represent trusted retrieval coverage and calculate deterministic missing request ranges.

**Contract:**

- Stored candles, retrieval coverage, expected-bar completeness and source policy are distinct.
- The planner operates on request and coverage intervals.
- It does not inspect or synthesize expected candles.
- It does not contact a broker or database.
- It does not normalize timestamps.

**Required evidence:** No coverage, full coverage, coverage outside the request, partial beginning/end, internal and multiple disjoint coverage, overlapping/touching/nested/duplicate coverage, permitted unordered input, and exact boundaries. See the [Validation Plan](../validation/VALIDATION_PLAN.md#m36b-coverage-and-missing-range-planning).

**Dependencies:** AD-008.

**Completion evidence:**

- Implementation commit: `1e8065a Add historical coverage planner`
- Focused historical coverage tests: 25 passed
- All market-data tests: 51 passed
- Full suite: 111 passed
- Interval contract: half-open `[start, end)`
- SQLiteCandleStore and HistoricalFeed behavior unchanged
- No provider, source-policy, or local-first orchestration added

### M3.6c — Local-first historical retrieval service

**Outcome:** A small orchestration boundary reads local candles, asks the planner for uncovered ranges, fetches only permitted gaps, validates provider output, persists accepted data and returns a canonical chronological result.

**Dependencies:** M3.6a and M3.6b; explicit provider empty/partial/failure semantics; approved timestamp-bound compatibility.

**Required evidence:** Fully cached requests avoid provider access; partial coverage fetches only gaps; exact overlaps reconcile safely; conflicts/failures do not create false coverage; fresh store instances can reuse accepted data.

**Completion evidence:**

- Implementation commit: `1c4a877 Add local-first historical retrieval`
- Focused M3.6c/store tests: 57 passed
- All market-data tests: 99 passed
- Full suite: 159 passed
- Post-commit full suite: 159 passed
- Explicit retrieval coverage is persisted independently of candles
- Fully covered requests avoid provider calls
- Only missing ranges are fetched
- Confirmed-empty and partial provider evidence are explicit
- Accepted candles and coverage are persisted transactionally
- SQLite chronological and range comparison uses parsed Python datetimes
- Mixed naive/aware dataset state is rejected
- Different aware offsets remain supported without normalization
- Equivalent aware timestamps at one instant have one candle identity
- HistoricalFeed, BaseBroker and AngelOne remain unchanged
- No source-policy, authentication or runtime wiring was added

### M3.6d — Integration and failure validation

**Status:** DONE.

**Outcome:** Prove the store, coverage representation, retrieval service and historical validation work together under success and failure.

**Required evidence:** Atomic consistency between accepted candles and coverage claims, durable reuse, partial-response handling, rollback/conflict behavior, and explicit errors for incompatible timestamp styles.

**Completion evidence:**

- Validation commit: `dc5bda3 Add M3.6d integration validation`
- Focused M3.6d integration suite: 11 passed
- M3.6 neighborhood: 93 passed
- All market-data tests: 110 passed
- Full suite: 170 passed
- Post-commit full suite: 170 passed
- No production-code correction required
- Cold-to-warm durable retrieval was proven
- Earlier accepted results survive later provider failure
- Partial results resume only remaining gaps
- Rollback is per accepted provider result
- Raw coverage rows integrate correctly with planner reconciliation
- Incompatible timestamp-awareness state fails safely before provider access
- Corrupt legacy duplicate logical timestamps are rejected, not repaired
- Half-open service semantics survive persistence and reload
- Confirmed-empty coverage is durably reusable
- `DatasetContext` isolation is preserved
- No source policy, broker authentication behavior, provider construction, HistoricalFeed wiring or M3.7 implementation was added

**M3.6 completion boundary:** M3.6a–M3.6d are DONE at the accepted local persistence, coverage-planning, retrieval-service and integration-validation scope. This does not establish runtime source selection, broker-free offline startup, historical-path parity, backtest validity, paper-trading readiness or V1 release readiness.

### M3.7 — Historical source policy/runtime wiring

**Status:** IN_PROGRESS.

**Outcome:** Put an explicit historical-source composition boundary above local persistence and external-provider capabilities, then wire backtest and WFA to it without moving source policy into broker adapters.

**Accepted policies:**

- `LOCAL_ONLY` uses persisted retrieval evidence only, never constructs or contacts an external provider, and fails with the remaining missing ranges when local coverage is incomplete.
- `LOCAL_FIRST` checks trusted local coverage first and constructs an external provider only after actual missing ranges are known. Complete local coverage requires no provider construction or broker authentication.
- `PROVIDER_BACKED` requires external provider access for the requested interval even when local coverage already exists. Existing local state remains available for persistence and conflict handling but cannot alone complete the request.

`RuntimeMode` selects the operation Kanasu runs; historical source policy selects where historical data may or must come from. These are independent configuration concerns. HistoricalFeed retains ownership of broker request limits, chunk traversal and broker-chunk validation/composition. See accepted AD-009 and the [Validation Plan](../validation/VALIDATION_PLAN.md#m37-historical-source-policy-runtime-wiring).

#### M3.7a — Historical source policy contract

**Status:** DONE.

**Outcome:** Define and test the policy-selection boundary for `LOCAL_ONLY`, `LOCAL_FIRST` and `PROVIDER_BACKED` using fake providers and factories.

**Required evidence:** `LOCAL_ONLY` never invokes a provider factory and fails clearly on incomplete coverage; fully covered `LOCAL_FIRST` avoids provider construction; missing `LOCAL_FIRST` coverage invokes the provider lazily; `PROVIDER_BACKED` requires provider access despite existing local coverage; source policy remains independent of `RuntimeMode`; and the policy contract introduces no broker-specific dependency.

**Completion evidence:**

- Implementation commit: `073f3e9 Add historical source policy contract`
- Focused M3.7a: 16 passed
- M3.6 + M3.7a neighborhood: 109 passed
- All market-data: 126 passed
- Full suite: 186 passed
- `HistoricalSourcePolicy` defines all three accepted policies
- `HistoricalSource` owns policy selection and lazy provider-factory use
- `LOCAL_FIRST` reuses `LocalFirstHistoricalService`
- Provider-result validation and half-open loading are shared behavior-preserving helpers
- Existing M3.6 behavior remains green
- No runtime wiring or broker adapter work occurred
- No destructive provider-backed refresh or replacement semantics were introduced

M3.7b is READY / NEXT after this documentation baseline is reviewed and committed; implementation is not authorized automatically and requires separate explicit authorization.

#### M3.7b — Broker historical provider adapter

**Status:** READY / NEXT.

**Outcome:** Provide a broker-backed `HistoricalProvider` adapter that collects the canonical `HistoricalFeed` stream, claims complete request coverage only after successful full stream completion, supports confirmed-empty retrieval, adapts the exact request-end boundary to half-open semantics, and preserves explicit timestamp-awareness validation.

**Ownership and contract:**

- The adapter implements the existing `HistoricalProvider` boundary and composes a supplied `HistoricalFeed`; it does not own authentication, source policy or runtime selection.
- HistoricalFeed remains authoritative for broker limits, chunk traversal, shared boundaries, overlap reconciliation, duplicate/conflict rejection, chronology and mixed-awareness stream validation.
- Successful completion for the full request returns `HistoricalFetchResult(candles=..., coverage=(request,))`. Coverage comes from successful operation completion, never candle count, first/last timestamps, spacing or expected bars. Sparse and empty successful streams retain full request coverage.
- If the feed or broker raises, the adapter raises and returns no result or coverage, even if earlier chunks emitted candles. M3.7b does not invent failed-stream partial coverage.
- The adapter includes a candle at `request.start` and excludes a candle exactly at `request.end` without epsilon or timeframe arithmetic. Other out-of-range candles are rejected through the shared provider-result validation boundary rather than silently clipped.
- Request and candle timezone awareness must be compatible. The adapter performs no UTC conversion, localization, offset stripping or silent naive/aware conversion.
- Accepted provider-result validation and canonical CandleSeries sequencing are reused rather than reimplemented.
- BaseBroker remains a broker capability beneath HistoricalFeed and does not acquire source-policy or HistoricalProvider responsibilities.

**AngelOne correction:** A valid successful response with `data = []` must return `[]`. Missing `data`, non-collection data, provider/API exceptions and other malformed responses remain errors. Normal non-empty response parsing must remain unchanged. This correction does not alter login, credentials, orders, runtime construction, request-format requirements or canonical timestamp policy.

**Required evidence:** Successful candles, sparse results, confirmed-empty results, request-start inclusion, exact request-end exclusion, failed streams with no manufactured coverage, explicit awareness mismatch, preserved HistoricalFeed chunk-validation regressions, valid empty AngelOne response, malformed AngelOne response rejection, and non-empty AngelOne parsing regression.

M3.7b adds no AppConfig, main, backtest, WFA, broker-factory, login-timing or source-policy runtime wiring. M3.7c and M3.7d remain PLANNED.

#### M3.7c — Backtest/WFA runtime wiring and lazy provider construction

**Status:** PLANNED.

**Outcome:** Make backtest and WFA consume historical candles through source composition instead of requiring immediate broker construction or owning source-selection logic.

**Required evidence:** `LOCAL_ONLY` and fully cached `LOCAL_FIRST` require no AngelOne credentials or login; missing `LOCAL_FIRST` coverage constructs the provider/broker only after gaps are known; and `PROVIDER_BACKED` requires the provider/broker.

#### M3.7d — Source-policy integration and failure validation

**Status:** PLANNED.

**Outcome:** Validate complete source-policy and research-runtime behavior under success and failure.

**Required evidence:** Fully local offline execution; warm `LOCAL_FIRST` operation without broker authentication; missing-gap provider fallback; mandatory `PROVIDER_BACKED` access; provider construction/login failure behavior; no false coverage after failure; confirmed-empty external results; explicit timestamp-awareness incompatibility; identical source-policy semantics in backtest and WFA; and DW-011 resolution evidence.

DW-011 remains OPEN until M3.7d closure.

### M3.8 — Historical-path parity and reproducibility

**Status:** RESERVED.

Candidate outcome: equivalent accepted data produces equivalent canonical candles, trades and account curves through provider-fresh and local-store paths, with an inspectable dataset/configuration identity.

## Remaining V1 milestones

### M4 — Backtest validity

Reserved scope includes declared timing/fill/stop assumptions, strategy/execution state agreement, account-based reporting, reproducible run manifests, deterministic reference scenarios, and removal of placeholder research results from authoritative workflows.

### M5 — WFA validity

Reserved scope includes finite expanding/rolling windows, complete configuration/economic propagation, leakage-resistant train/test separation, account-valid metrics, an explicit overlap/stitching policy and reproducible per-window evidence.

### M6 — Live market-data foundation

Reserved scope includes one real provider, completed-candle semantics, sequence validation, freshness/disconnect behavior and diagnostic recording. It does not include real-money orders.

### M7 — Paper-session integration

Reserved scope includes a real-data feed, strategy, risk, simulated execution, authoritative portfolio, journal, snapshots, truthful start/stop/failure states, and a recovery policy.

### M8 — Research and paper application

Reserved scope includes actual research jobs/results, dataset/source visibility, portfolio/trade/equity views, paper controls, errors and a responsive browser interface. Delivery should use small backend-to-UI vertical slices.

### M9 — V1 validation and release

Reserved scope includes reproducible reference results, subsystem and workflow evidence, failure scenarios, paper observation, documentation synchronization and all mandatory V1 release gates.

## V2 and progressive horizons

**V2 — Controlled Real-Money Execution** follows V1 acceptance. Its detailed milestone identifiers are intentionally not allocated. It requires order identity, acknowledgement/rejection/cancellation/partial-fill semantics, reconciliation, restart recovery, operational risk controls, restricted rollout and applicable external acceptance.

V3+ candidates include multi-symbol portfolio research, scanners and market intelligence, fundamentals, derivatives, additional brokers/markets, advanced statistical/ML research, optional multi-user delivery and eventually native mobile. These are progressively elaborated in the [Product Vision](../PRODUCT_VISION.md) and [AI Research Backlog](AI_RESEARCH_BACKLOG.md); they are not current commitments.

## Progress measurement

Unsupported overall project percentages are prohibited.

Future baselined scopes may estimate leaf tasks with 1, 2, 3, 5, 8 or 13 effort points and report implementation and validation separately. Do not use lines of code, number of tests, calendar time, or number of roadmap headings as completion percentages. Do not retroactively invent estimates for completed historical work merely to produce a percentage. Parent and child effort must not be double-counted.

## Historical identifiers

M0–M3 and their existing children are permanent. Old roadmap table serials, Phase 8 and 10.9B/C/D labels are historical terminology, not modern milestone identifiers. Their provenance and crosswalk are retained in the [Legacy Project Snapshot](../archive/LEGACY_PROJECT_SNAPSHOT.md).
