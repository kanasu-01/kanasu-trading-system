# Kanasu Validation Plan

## 1. Purpose

This document owns subsystem Definitions of Done, evidence requirements and release gates. It distinguishes implementation, integration, validation and release readiness.

A passing focused test proves only the declared behavior under that test's conditions. It does not establish profitability, provider completeness, end-to-end integration or release readiness.

## 2. Evidence model

Each roadmap task should identify:

- the behavior and failure behavior being established;
- focused tests or other deterministic evidence;
- required integration and regression checks;
- relevant environment, dataset, configuration and revision;
- material limitations that remain; and
- affected authoritative documentation.

A task may be DONE only when its accepted evidence and required documentation synchronization are complete.

## 3. Subsystem Definitions of Done

### Candle and data contracts

- Valid and invalid OHLCV controls cover the declared contract.
- Timestamp fidelity, chronology, duplicates and timezone-awareness behavior are explicit at the relevant boundary.
- Rejected data cannot mutate accepted sequence state.
- No sorting, deduplication, localization, conversion, gap filling or repair occurs unless an accepted contract explicitly owns it.
- Source-specific parsing does not leak raw provider structures downstream.

### Storage

- Dataset and candle identity are explicit and deterministic.
- Round-trip fidelity covers supported timestamps and OHLCV.
- Range semantics and chronological reads are verified.
- Exact duplicates are idempotent and conflicting duplicates are rejected.
- Batch writes are genuinely atomic.
- Writes are durably visible to a new store instance.
- Schema evolution, backup and concurrency behavior are defined before operational reliance requires them.

### Coverage and retrieval

- Retrieval coverage has an explicit interval and evidence contract.
- Missing-range planning is deterministic and boundary behavior is tested.
- Stored candles are not mistaken for retrieval coverage.
- Retrieval coverage is not mistaken for expected-bar completeness.
- Empty, partial, failed and conflicting provider responses have explicit outcomes.
- Accepted candles and any resulting coverage claim remain transactionally consistent.
- Local-only behavior performs no provider authentication or network request.
- Returned candles pass the canonical integrity boundary.

### Execution and accounting

- Fill-price, slippage and explicit-cost ownership are tested.
- Open, mark and close accounting preserves portfolio invariants.
- Same-bar entry/stop causality and subsequent-bar stops are tested.
- Brokerage-enabled and disabled behavior are independent of slippage.
- Execution reporting uses actual simulated fills.
- Strategy, execution and portfolio position state cannot silently diverge.
- Stop/gap, affordability, sizing and drawdown semantics are documented and tested to the level required by the selected research strategy.

### Backtest

- A deterministic fixture produces known signals, trades and account results.
- Input dataset identity and effective strategy/execution/risk configuration are retained.
- Timing, fill, stop and end-of-data assumptions are explicit.
- Equity, drawdown and return metrics use the intended account basis.
- Repeated runs from the same manifest produce equivalent results.
- API and exported results originate from the actual engine rather than fixtures or placeholders.

### Walk-Forward Analysis

- Rolling and expanding windows terminate and match declared boundaries.
- In-sample selection never consumes out-of-sample observations.
- Capital, runtime economics, dataset identity and strategy parameters propagate unchanged unless explicitly varied.
- Metrics distinguish instrument, trade and account returns.
- Empty/insufficient samples and failed windows are represented truthfully.
- Overlapping out-of-sample windows and equity stitching have an explicit policy.
- Each selected parameter set and out-of-sample result is reproducible.

### Live market data

- One provider delivers canonical completed candles with declared timestamp semantics.
- Duplicates, regressions, conflicts and mixed awareness are handled explicitly.
- Freshness, disconnect, reconnect and partial-candle behavior are observable and tested.
- Diagnostic recording can reproduce relevant feed failures.
- A feed failure cannot be reported as a healthy running session.

### Paper runtime

- The session owns one feed/strategy/risk/simulated-execution/portfolio lifecycle.
- It consumes real market data for the V1 operational mode.
- Start, running, stopping, stopped and failed states reflect the actual runtime.
- Stop and end-of-stream behavior release resources predictably.
- Journals and snapshots reflect authoritative execution/portfolio state.
- Restart/recovery policy and unsupported cases are explicit.
- No real-money order route is reachable in V1.

### API

- Endpoints operate real authorized workflows or identify explicit mock/development responses.
- Request validation, errors, status and identifiers are stable and tested.
- Reported job/session state matches actual backend state.
- Long-running work has a defined lifecycle and cancellation policy.
- Deployment security and authorization match the exposure of the service.

### Frontend

- Displayed metrics and states come from authoritative API responses.
- Loading, empty, error, stopped and failed states are visible.
- Backtest and paper modes are labelled accurately.
- Core workflows work at supported desktop and mobile-browser sizes.
- Setup/build/lint instructions match package scripts.
- Placeholder UI cannot be mistaken for validated product behavior.

### Documentation

- One authoritative owner exists for each fact.
- Current, target and historical statements are clearly labelled.
- Permanent IDs and historical crosswalks are preserved.
- Relative links resolve and moved paths have no active references.
- Project Status records dated evidence without claiming checks that were not run.
- Architecture decisions and deferred issues reflect material contract changes.

### Eventual V2 live execution

- Broker order acknowledgement, rejection, cancellation and partial/full fill lifecycles are verified.
- Client/order identity and retries are idempotent.
- Broker orders, fills, positions, cash and charges reconcile with local state.
- Restart and unknown-state recovery are tested.
- Stale feeds, disconnects and broker failures trigger defined safe behavior.
- Exposure limits, operator stop controls and restricted rollout are verified.
- Applicable broker, exchange and regulatory requirements are reviewed and accepted.

<a id="m36b-coverage-and-missing-range-planning"></a>

## 4. M3.6b — Coverage and missing-range planning

M3.6b deals only with retrieval coverage and deterministic missing-range planning. Request, coverage and returned missing ranges use half-open `[start, end)` intervals: start is included and end is excluded. It excludes broker/provider wiring, SQLite orchestration, expected-bar generation, market or holiday calendars, timezone conversion, arbitrary naive/aware normalization and source-policy implementation.

The planner contract does not change SQLiteCandleStore.load(), whose candle-read range is inclusive at both ends. Any adapter between those semantics belongs to M3.6c.

Required focused cases:

1. No coverage returns the requested interval.
2. Full coverage returns no missing interval.
3. Coverage entirely before the request does not reduce it.
4. Coverage entirely after the request does not reduce it.
5. Partial coverage at the beginning leaves the uncovered end.
6. Partial coverage at the end leaves the uncovered beginning.
7. An internal covered interval produces two missing intervals.
8. Multiple disjoint covered intervals produce all missing intervals.
9. Overlapping coverage intervals are reconciled for planning.
10. Touching intervals are continuous coverage under the half-open convention.
11. Nested intervals do not create false gaps.
12. Duplicate intervals do not change the result.
13. Unordered intervals are accepted and normalized deterministically.
14. Coverage extending outside the request is clipped to the request.
15. Exact request-start and request-end boundaries obey `[start, end)`.
16. Invalid request or coverage intervals are rejected explicitly.
17. Incompatible naive/aware timestamps produce a clear error rather than implicit conversion.

Acceptance evidence must show that returned missing ranges are chronological, non-overlapping and non-empty. It must not infer expected market bars from coverage.

<a id="m36c-local-first-historical-retrieval-service"></a>

## 5. M3.6c — Local-first historical retrieval service

M3.6c composes persistent retrieval coverage, the M3.6b planner, an injected provider contract, and local candle persistence. Service requests and provider coverage use half-open `[start, end)` intervals. `SQLiteCandleStore.load()` remains inclusive at both ends; the service adapter excludes a candle exactly at the request end without using a datetime epsilon or timeframe duration.

Required focused evidence:

1. A fully covered request, including sparse or confirmed-empty local data, makes no provider call.
2. Stored candles without retrieval coverage still require provider evidence.
3. Partial coverage and multiple coverage islands request only the planned missing gaps.
4. Full provider success persists candles and explicit coverage for reuse by a fresh store/service instance.
5. Confirmed-empty coverage is persisted without inferring expected bars.
6. A partial provider result persists only its claimed coverage, reports the remaining gaps, and a later call requests only those gaps.
7. Provider failure or missing coverage evidence creates no false coverage claim.
8. Coverage outside the requested gap, candles outside the gap or explicit coverage, incompatible timezone awareness, and malformed candle sequences are rejected before persistence.
9. Exact stored candle overlap is idempotent; conflicting overlap rolls back new candles and coverage from that provider result.
10. Candle and coverage state remain isolated by complete `DatasetContext` identity.
11. SQLite candle and coverage writes are transactional and durably visible across instances.
12. SQLite inclusive reads filter and order parsed datetimes with Python comparison semantics across aware offsets, reject naive/aware incompatibility clearly, and preserve timestamp offsets and precision without conversion. Each `DatasetContext` persists one awareness style across candle and coverage timestamps, while differing aware offsets remain valid. Equivalent aware timestamps with different serialized offsets form one candle identity while retaining the first stored representation; conflicting OHLCV is rejected transactionally.
13. The half-open service result includes the request start and excludes the request end while leaving the inclusive store API unchanged.

Acceptance evidence must confirm that M3.6c adds no broker authentication, provider construction, runtime source-policy selection, expected-bar logic, calendar/session inference, or timestamp normalization. DW-010 is resolved for the accepted M3.6c timestamp-compatibility scope; DW-014 retains indexing, scalability and legacy-state migration concerns.

<a id="m36d-integration-and-failure-validation"></a>

## 6. M3.6d — Integration and failure validation

M3.6d validates the existing M3.6 storage, retrieval coverage, missing-range planning, local-first retrieval, provider-result validation and canonical CandleSeries sequence boundary together. It does not redefine their accepted contracts.

Required integration evidence:

1. Complex cold retrieval across multiple planned gaps persists accepted results and becomes a warm retrieval requiring no provider call through a fresh store/service instance.
2. An earlier accepted provider result remains durable when a later gap's provider call fails, and gaps after that failure are not requested during the failed call.
3. Partial provider evidence persists only its explicit subset, the final incomplete error identifies the actual remaining ranges, and a later call resumes only those ranges.
4. A conflicting later provider result rolls back its new candles and coverage while preserving results accepted for earlier gaps.
5. Raw overlapping and touching coverage rows remain unmodified in storage and are reconciled by the M3.6b planner.
6. Incompatible persisted/request timezone awareness fails before provider access without mutating accepted state.
7. Legacy or corrupt cross-offset duplicate logical timestamps are rejected by CandleSeries validation without silent deduplication, repair or normalization.
8. The half-open service result includes the request start and excludes its end after durable SQLite reload.
9. Confirmed-empty coverage remains reusable across fresh instances without provider access.
10. Candles and coverage remain isolated by complete `DatasetContext` identity through retrieval lifecycles.

Atomicity is per accepted provider result, not one transaction spanning the entire multi-gap `retrieve()` call. M3.6d adds no source-policy, broker-authentication or provider-construction behavior.

<a id="m37-historical-source-policy-runtime-wiring"></a>

## 7. M3.7 — Historical source policy/runtime wiring

M3.7 must establish explicit `LOCAL_ONLY`, `LOCAL_FIRST` and `PROVIDER_BACKED` source-policy behavior while preserving the accepted M3.6 storage, coverage, retrieval and timestamp contracts. M3.7a and M3.7b are DONE and validated at their accepted isolated scopes. M3.7c and M3.7d are PLANNED and not yet validated. M3.7 as a whole is not yet validated.

Cross-step invariants:

1. `LOCAL_ONLY` never invokes a provider factory, constructs a broker or authenticates externally; incomplete local coverage fails with the remaining missing ranges.
2. Fully covered `LOCAL_FIRST` retrieval never invokes a provider factory, constructs a broker or authenticates externally.
3. Missing `LOCAL_FIRST` coverage constructs the provider lazily only after gaps are known and fetches only those gaps.
4. `PROVIDER_BACKED` requires provider access for the requested interval even when local coverage exists.
5. Broker authentication occurs only when external capability is required by policy and request state.
6. Stored candles, retrieval coverage, expected-bar completeness and source policy remain distinct; M3.6 half-open coverage and transactional evidence semantics remain unchanged.
7. A successfully confirmed empty external response can provide explicit coverage; coverage is never inferred from candle count, first/last timestamps, spacing or expected bars.
8. Provider failure or malformed results create no false coverage.
9. Historical source policy is independent of `RuntimeMode`.
10. Backtest and WFA ultimately consume identical source-policy semantics without owning source selection.
11. No expected-bar, market-calendar, holiday or session inference is introduced.
12. No timestamp normalization, localization, offset stripping or silent naive/aware conversion is introduced; request/provider awareness compatibility is explicit.

### M3.7a — Historical source policy contract

**Status:** DONE

**Implementation commit:** `073f3e9 Add historical source policy contract`

**Evidence:** Focused M3.7a: 16 passed; M3.6 + M3.7a neighborhood: 109 passed; all market-data: 126 passed; full suite: 186 passed.

Validated behavior:

1. Complete `LOCAL_ONLY` coverage returns local candles with zero provider-factory calls.
2. Confirmed-empty `LOCAL_ONLY` coverage returns an empty result with zero provider-factory calls.
3. Incomplete `LOCAL_ONLY` coverage reports the exact missing ranges.
4. Stored candles without retrieval coverage do not establish completeness.
5. Warm `LOCAL_FIRST` retrieval performs zero provider construction.
6. Missing `LOCAL_FIRST` coverage constructs one provider lazily.
7. One provider instance serves multiple missing ranges in one retrieval operation.
8. `PROVIDER_BACKED` accesses the provider for the complete request despite complete local coverage.
9. Confirmed-empty full provider evidence is accepted.
10. Provider-backed completeness uses only the current provider result's explicit coverage.
11. Old local coverage cannot mask partial provider evidence.
12. Provider access required by policy fails clearly when no provider factory is available.
13. Provider-backed retrieval reuses the accepted provider-result validation boundary.
14. All policies reuse the accepted M3.6 half-open result semantics.
15. Historical source policy remains independent of `RuntimeMode`.
16. The policy boundary introduces no dependency on BaseBroker, AngelOne or another broker implementation.

Provider-backed cache refresh or replacement semantics remain undefined and persistence remains non-destructive. Broker adapter behavior belongs to M3.7b. Runtime configuration, runtime wiring and lazy broker login belong to M3.7c. End-to-end policy/runtime validation belongs to M3.7d.

### M3.7b — Broker historical provider adapter

**Status:** DONE / validated

Required acceptance evidence:

1. A successfully completed HistoricalFeed stream returns canonical collected candles with explicit coverage for the complete request.
2. A successfully completed empty stream returns `candles = ()` and `coverage = (request,)`.
3. Sparse candle presence does not reduce retrieval coverage or trigger expected-bar inference.
4. A candle exactly at `request.start` is included.
5. A candle exactly at `request.end` is excluded without datetime epsilon or timeframe arithmetic.
6. A candle strictly outside the half-open request is rejected through the shared provider-result validation contract rather than silently clipped.
7. If HistoricalFeed or its broker fails after emitting earlier chunks, the adapter raises and returns no HistoricalFetchResult or coverage.
8. Request/candle naive-aware incompatibility fails explicitly without conversion, localization or offset stripping.
9. Existing HistoricalFeed tests remain authoritative and green for chunk traversal, shared boundaries, overlap, duplicates, conflicts, chronology and mixed awareness; the adapter must not bypass or duplicate those responsibilities.
10. The adapter reuses `validate_historical_fetch_result()` and canonical CandleSeries sequence behavior where applicable.
11. A valid AngelOne response containing `data = []` returns an empty candle list.
12. Missing `data`, invalid/non-collection data, and provider/API failure remain errors rather than confirmed-empty evidence.
13. A valid non-empty AngelOne response retains the existing timestamp and OHLCV parsing behavior.
14. BaseBroker remains unchanged as a broker capability and does not become a HistoricalProvider or source-policy owner.

Completion evidence:

- Implementation commit: `b6a4fff Add broker historical provider adapter`
- Pre-change full suite: 186 passed
- Focused HistoricalFeedProvider: 10 passed
- Focused AngelOne historical: 10 passed
- HistoricalFeed regressions: 15 passed
- M3.7 neighborhood: 90 passed
- All market-data: 136 passed
- Broker neighborhood: 10 passed
- Full suite: 206 passed
- `git diff --check`: passed

This evidence validates the isolated broker-backed provider capability and the minimal AngelOne confirmed-empty correction. It does not validate runtime construction, login timing, backtest/WFA wiring or M3.7 end-to-end behavior.

Coverage is evidence of successful complete retrieval, not an inference from candle content. No market-calendar, holiday, session, expected-bar, gap-filling or provider-backed destructive refresh behavior belongs to M3.7b. Runtime configuration, provider construction/login timing, main, backtest and WFA wiring remain M3.7c work; end-to-end policy behavior remains M3.7d work.

### M3.7c — Backtest/WFA runtime wiring and lazy provider construction

**Status:** PLANNED / not yet validated

Prove that backtest and WFA obtain historical candles through the source-composition boundary. `LOCAL_ONLY` and warm `LOCAL_FIRST` runs require no AngelOne credentials, construction or login; missing `LOCAL_FIRST` coverage constructs external capability only after gaps are known; `PROVIDER_BACKED` requires it. Neither runtime may duplicate policy decisions.

### M3.7d — Source-policy integration and failure validation

**Status:** PLANNED / not yet validated

Prove fully local offline operation, warm local-first operation without authentication, missing-gap fallback, mandatory provider-backed access, provider-construction/login failure behavior, absence of false coverage after failure, confirmed-empty external behavior, explicit awareness incompatibility, and common backtest/WFA semantics. DW-011 may close only with this accepted runtime evidence.

## 8. V1 release gates

V1 is release-ready only when all mandatory gates pass:

- trusted historical local-first retrieval and parity;
- reproducible dataset/configuration identity;
- validated backtest timing/economics/account metrics;
- validated WFA windows, propagation and metrics;
- operational real-market-data paper ingestion;
- truthful paper-session lifecycle and authoritative portfolio state;
- durable journals/results adequate for investigation;
- real API workflows and responsive UI;
- documented limitations and failure behavior; and
- an explicit confirmation that real-money execution is unavailable.

Progress in one gate cannot compensate for a failed mandatory gate.
