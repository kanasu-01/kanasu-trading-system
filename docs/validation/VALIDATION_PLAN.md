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

**Accepted M6/M7 evidence through `7dd8e34`:** AngelOne real market data is wired into the paper runtime; live execution obeys causal source-event next-bar semantics; provider lifecycle/failure/retry behavior is supervised; post-gap continuation requires explicit reconciliation; authoritative PortfolioManager-backed snapshots and per-session journals are available; runtime session IDs are unique; and retry settings load from environment. The final local M7.9 suite passed 725 tests and GitHub Actions Run 92 succeeded.

The implementation currently exposes `CREATED`, `RUNNING`, `STOPPED` and `FAILED`; it does not expose separate `STARTING`/`STOPPING` states. M8/M9 must either add those public transitional states or explicitly validate/document the accepted lifecycle. API/frontend ownership remains M8 work.

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

### M8 — Research and Paper Application

**Status:** DESIGN BASELINE / implementation not yet validated

M8 validates the application boundary without reopening accepted M4/M5/M7 trading semantics. Required evidence is:

1. Backtest request models reject malformed dates, invalid ranges, non-finite/non-positive capital and unsupported strategy/config values before authoritative execution.
2. The initial V1 application advertises only strategies that are intentionally supported by the application contract; `camarilla` drift is removed and PivotBoss is not presented as validated.
3. `POST /api/backtest/run` executes the real historical-source → validated strategy → `BacktestEngine` path rather than returning a fixture or fixed identifier.
4. Blocking Backtest execution runs outside the FastAPI event loop and the initial request-scoped synchronous lifecycle is deterministic and tested.
5. The returned run identifier equals the actual `BacktestResult.session_id`.
6. Backtest summary metrics come from `PerformanceMetrics.summarize_backtest()` and preserve M4.4 account/trade terminology.
7. Returned equity points and completed trades are projections of the actual `BacktestResult`; empty-result and failure cases are represented truthfully.
8. Paper start constructs and starts the actual M7 paper runtime and exposes the same authoritative `PaperTradingSession` used by execution.
9. Application ownership permits at most one active paper session initially; duplicate start has a stable conflict response and cannot create a second live worker.
10. Paper status is derived from `PaperTradingSession.snapshot()`, includes authoritative lifecycle, portfolio, active-position, latest-execution and failure fields, and cannot expose a torn snapshot across concurrent paper-state mutation; reads are serialized or use equivalent atomic immutable publication.
11. Paper stop invokes the real `LivePaperRuntime.stop()` path, waits for worker termination and cannot succeed merely by mutating metadata.
12. Runtime/provider failure propagates to terminal `FAILED` state with truthful failure information and no false healthy status.
13. The latest terminal `STOPPED` or `FAILED` snapshot remains observable after worker termination and is replaced only by a later successful start.
14. The accepted public lifecycle remains `CREATED`, `RUNNING`, `STOPPED` and `FAILED` unless a separately reviewed contract change adds transitional states.
15. Frontend code consumes backend-authoritative cash, position, equity, P&L, drawdown, trade/execution and lifecycle state and does not independently reconstruct them.
16. Frontend API base configuration is environment/application configuration rather than a machine-specific hard-coded URL.
17. Frontend type checking/build/lint and focused interaction tests cover Backtest and Paper loading, empty, running, stopped, failed and request-failure states at supported responsive sizes.
18. No placeholder Backtest result, paper metadata session or commented/inert UI path is presented as validated application behavior.
19. M8 changes do not silently alter M4/M5 Backtest/WFA economics, M7 causal paper execution/reconciliation, real-money execution boundaries, multi-symbol semantics or PivotBoss validation.
20. M8 closure updates authoritative documentation and dispositions DW-013 with implementation evidence. DW-015 remains independently scoped unless separately approved.

M9 remains responsible for final V1 end-to-end acceptance and release validation.

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

M3.7 establishes explicit `LOCAL_ONLY`, `LOCAL_FIRST` and `PROVIDER_BACKED` source-policy behavior while preserving the accepted M3.6 storage, coverage, retrieval and timestamp contracts. M3.7a, M3.7b, M3.7c and M3.7d are DONE and validated at their accepted scopes; M3.7 is complete.

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

**Status:** DONE / validated at M3.7c scope

M3.7c proves runtime dependency wiring, source composition and lazy external construction without taking on the wider M3.7d failure matrix.

Validated behavior:

1. Constructing historical source composition alone does not call `AngelOneConfig.load_from_env`, construct a broker or call broker login.
2. `LOCAL_ONLY` with complete local coverage performs no external construction or login.
3. Fully cached `LOCAL_FIRST` performs no external construction or login.
4. Missing `LOCAL_FIRST` invokes the lazy provider only after local retrieval coverage has been examined.
5. `PROVIDER_BACKED` invokes the external provider despite complete local coverage.
6. Backtest retrieves candles through HistoricalSource and has no HistoricalFeed or BaseBroker dependency.
7. WFA retrieves candles through the same HistoricalSource boundary and has no HistoricalFeed or BaseBroker dependency.
8. Backtest and WFA do not duplicate `LOCAL_ONLY`, `LOCAL_FIRST` or `PROVIDER_BACKED` branching.
9. Main performs no unconditional broker construction or login before selecting a runtime mode.
10. The lazy historical provider path calls the existing broker factory with `paper_mode=True` and `enable_historical_api=True`, then composes HistoricalFeed and HistoricalFeedProvider.
11. Existing HistoricalSource, HistoricalFeedProvider, HistoricalFeed, AngelOne historical, market-data and broader regression suites remain green.
12. Historical request timestamps pass through unchanged; no UTC normalization, localization, offset stripping or silent awareness conversion is added.
13. Incompatible request/provider timezone awareness remains an explicit failure.

Configuration evidence establishes that AppConfig owns `historical_source_policy`, `historical_database_path` and `historical_request_delay_sec`, with accepted defaults `LOCAL_FIRST`, `data/historical.sqlite3` and `0.5`. The repository's default AngelOne-oriented BacktestConfig uses explicit timezone-aware Asia/Kolkata request bounds without creating an automatic DatasetContext-timezone localization rule.

Completion evidence:

- Parent design/baseline commit: `81600de275bf41d0dc75ea8b0c220dd4c2643eec Baseline M3.7c runtime wiring and lazy provider construction`
- Implementation commit: `2db07c6da3af9a6434c51bfe1e629af65a001710 Wire historical source into research runtimes`
- Pre-change full suite: 206 passed
- Historical source factory: 11 passed
- Runtime tests: 11 passed
- HistoricalSource/feed/AngelOne neighborhood: 51 passed
- All market-data: 147 passed
- Backtest/WFA/runtime: 22 passed
- Post-change full suite: 223 passed
- `git diff --check`: passed
- Validation interpreter: `.\.venv\Scripts\python.exe`, Python 3.11.9

M3.7c does not validate fully offline end-to-end execution, missing credential behavior, provider construction/login failures, false-coverage prevention after failures, confirmed-empty cross-policy integration, identical complete Backtest/WFA policy semantics or DW-011 closure. Those remain M3.7d acceptance work.

### M3.7d — Source-policy integration and failure validation

**Status:** DONE / validated

M3.7d validates the implemented components together through the bounded historical-source/research-runtime path:

~~~text
main runtime selection
        ↓
historical source composition
        ↓
HistoricalSource and source policy
        ↓
SQLite/local retrieval
        ↓ only when required
lazy provider factory
        ↓
broker factory/authentication seam
        ↓
HistoricalFeed → HistoricalFeedProvider
        ↓
canonical candles → Backtest or WFA runtime
~~~

This is not validation of backtest economics, strategy correctness, WFA optimization validity, paper/live trading, UI, or real broker/network operation. All cases must be deterministic and must not contact AngelOne.

#### A. Fully local offline execution

For both BACKTEST and WALK_FORWARD, pre-populate trusted SQLite candles and coverage, select `LOCAL_ONLY`, execute through actual source composition and runtime boundaries, verify canonical candles reach the runtime, and prove zero credential loading, broker construction, login, and provider access.

#### B. Warm LOCAL_FIRST offline execution

For both runtimes, use complete trusted local coverage and prove successful operation with zero credential loading, broker construction, login, and provider access. This is mandatory DW-011 resolution evidence.

#### C. Missing LOCAL_FIRST coverage

Prove local coverage is examined first, provider construction occurs only after actual missing ranges are known, only those ranges are requested, successful provider evidence becomes durable retrieval coverage, and a later warm retrieval avoids external access. Do not infer expected bars.

#### D. PROVIDER_BACKED mandatory access

Prove complete local coverage does not suppress provider access and completion depends on fresh explicit provider coverage evidence.

#### E. Credential, construction, and login failures

Prove absent credentials do not affect `LOCAL_ONLY` or fully covered `LOCAL_FIRST`. When policy requires a provider, credential loading, construction, or login failure must surface explicitly, manufacture no coverage, preserve valid local state, and disclose no credentials or sensitive values. Use deterministic fakes or monkeypatching at the existing broker-factory seam.

#### F. Retrieval failure and false-coverage prevention

When provider construction succeeds but retrieval fails, the failing request or range gains no coverage. Earlier provider results already committed under M3.6 semantics remain valid; they are not globally rolled back. Retry planning requests only genuinely remaining gaps.

#### G. Confirmed-empty external results

Prove a successful empty response creates explicit durable coverage, later warm `LOCAL_FIRST` and `LOCAL_ONLY` reuse it without provider access, and a later `PROVIDER_BACKED` request still requires provider access. Candle absence is not retrieval failure.

#### H. Timestamp-awareness incompatibility

Prove incompatible persisted/request awareness fails before unnecessary provider access when knowable locally, incompatible request/provider evidence fails explicitly, failed evidence creates no coverage, and no UTC conversion, localization, offset stripping, or silent awareness conversion occurs. DatasetContext timezone remains metadata.

#### I. Common Backtest/WFA semantics

Use shared or parameterized integration cases where clear to prove Backtest and WFA receive equivalent historical-source behavior for the same DatasetContext, TimeRange, policy, local state, and provider outcome. Their trading and research outputs are outside this validation scope.

#### Failure and implementation requirements

Expected production-code changes are none unless focused integration RED evidence proves an existing-contract defect. Any correction must identify the failing contract and exact file, apply Governance implementation-quality requirements, and remain the smallest coherent fix. Validate explicit errors, false/corrupt-state prevention, useful diagnostics, secret-safe failures, SQLite/resource safety, and risk-proportionate success, boundary, failure, and regression behavior without adding boilerplate.

M3.7d must not add real network calls, calendar/session/expected-bar inference, candle-spacing gap inference, timestamp normalization, destructive provider refresh, broker-owned source policy, broker-factory redesign, M3.8/M4/M5 work, PAPER/LIVE historical integration, or frontend/API behavior.

#### Completion evidence

- Design baseline: `0726b148`
- Implementation and validation commit: `7f968843 Validate M3.7d source-policy integration`
- Pre-change full suite: 223 passed
- Focused M3.7d integration: 17 passed
- Regression neighborhood: 71 passed
- All market-data: 147 passed
- Runtime / Backtest / WFA: 39 passed
- Post-change full suite: 240 passed
- `git diff --check`: passed
- Production corrections: none
- Test changes: +722 / -0 in `tests/runtime/test_historical_source_policy_integration.py`

The accepted evidence validates M3.7d through the bounded historical-source/research-runtime path. No production correction was required. M3.7a, M3.7b, M3.7c and M3.7d are validated at their accepted scopes, so M3.7 is complete and DW-011 is resolved at that scope. These validation claims do not extend into M3.8 historical-path parity, M4 backtest validity or M5 WFA validity.

<a id="m38-historical-path-parity-and-reproducibility"></a>

## 8. M3.8 — Historical-path parity and reproducibility

**Status:** DONE / validated at accepted scope through completed M3.8a–M3.8d

M3.8 validates that equivalent accepted historical data and the same research-relevant configuration yield equivalent canonical historical inputs and stable deterministic Backtest outputs through provider-fresh and already persisted local-store paths. It also requires deterministic dataset, configuration and result identities plus inspectable research-evidence persistence. It does not validate Backtest economics or WFA validity.

### M3.8a — Historical input parity

**Status:** DONE / validated at accepted scope

Authoritative automated tests must use deterministic fake/provider and local-store evidence without broker login or network access. For equivalent accepted data, provider-fresh and warm-local paths must produce equal:

1. candle count;
2. chronological order;
3. timestamps;
4. open, high, low, close and volume values;
5. `DatasetContext`;
6. requested half-open `TimeRange` behavior; and
7. confirmed-empty results where applicable.

Source provenance may differ and must be recorded separately; it must not alter otherwise identical canonical candle content.

Completion evidence:

- Design baseline: `c53c640`
- Implementation commit: `0a8410ff Validate M3.8a historical input parity`
- Pre-change full suite: 240 passed
- Focused M3.8a: 5 passed
- Source-policy regression: 33 passed
- All market-data: 152 passed
- Post-change full suite: 245 passed
- `git diff --check`: passed
- Production corrections: none

This evidence validates provider-fresh to durable-local parity through `LOCAL_ONLY` and warm `LOCAL_FIRST`, with equal chronology, timestamp representation and OHLCV values. It also validates half-open request boundaries, confirmed-empty durability, `DatasetContext` isolation and deterministic execution without an external provider, network or credentials. No production correction was required.

### M3.8b — Backtest result parity

**Status:** DONE / validated at accepted scope

With identical canonical candles and research-relevant configuration, provider-fresh and warm-local runs must have equivalent stable detailed Backtest results. Compare applicable trades, entry/exit timestamps, direction, prices, quantity, exit reason, gross/net P&L, transaction costs, stable bar-level strategy/execution events, execution prices/quantities, cash, equity, position size, drawdown and canonical equity curve.

`BacktestResult.session_id` is intentionally excluded because it is execution-instance identity. Any other nondeterministic field excluded from parity requires explicit justification. Performance-summary equality is supporting evidence only and cannot replace detailed stable-result comparison.

Completion evidence:

- Design baseline: `c53c640`
- Implementation commit: `388b5393 Validate M3.8b backtest result parity`
- Pre-change full suite: 245 passed
- Focused M3.8b: 3 passed
- Parity/Backtest neighborhood: 12 passed
- All Backtest tests: 4 passed
- All runtime tests: 31 passed
- Post-change full suite: 248 passed
- `git diff --check`: passed
- Production corrections: none
- Test scope: `tests/runtime/test_backtest_result_parity.py`, +304 / -0

M3.8b validates reproducibility of the current deterministic Backtest result contract across provider-fresh and durable-local historical paths. Complete `Trade` records, `BarRecord` sequences, execution events/prices/quantities, cash, equity, position size, drawdown and equity curves remained exactly equal. Session IDs were deliberately different, confirming that execution-instance identity is excluded from stable-result parity. No production correction was required.

This evidence does not establish whether Backtest economics, timing, fills, stops, slippage, brokerage or account metrics are financially correct. Those remain M4 concerns.

### M3.8c — Reproducibility identity and research-evidence persistence

**Status:** DONE / validated at accepted scope

M3.8c validates the AD-015 versioned, type-tagged canonical serialization contract; independent SHA-256 dataset, effective Backtest-configuration and stable-result domains; immutable evidence status/model rules; and dedicated SQLite evidence persistence separate from historical candles and coverage.

Validated deterministic evidence:

1. Repeated serialization of identical input produces identical canonical bytes and fingerprint.
2. Mapping insertion order does not alter canonical identity.
3. Finite float values use exact deterministic `float.hex()` representation.
4. Non-finite floats fail explicitly.
5. Unsupported canonical value types fail explicitly rather than being stringified.
6. Datetime representation is deterministic, uses microsecond precision and preserves supplied timezone/offset semantics without normalization.
7. Equivalent provider-fresh and durable-local canonical datasets produce equal dataset fingerprints.
8. Changing `DatasetContext` changes dataset identity.
9. Changing the requested `TimeRange` changes dataset identity.
10. Changing canonical candle content changes dataset identity.
11. Noncanonical candle ordering is rejected rather than silently sorted.
12. Changing provenance or source policy alone does not change dataset identity.
13. Equivalent strategy-parameter mappings with different insertion order produce the same configuration fingerprint.
14. Changing strategy name or research parameters changes configuration identity.
15. Changing initial capital changes configuration identity.
16. Changing explicitly supplied effective risk-per-trade changes configuration identity.
17. Changing slippage percentage or slippage-enabled state changes configuration identity.
18. Changing brokerage-enabled state changes configuration identity.
19. Presentation-only replay, visualization and export controls do not alter research-configuration identity.
20. Equivalent stable Backtest results with different session IDs produce identical result fingerprints.
21. Changing a stable `Trade` field changes result identity.
22. Changing a stable `BarRecord` or account-state field changes result identity.
23. Decision-snapshot mapping order does not alter result identity, while unsupported snapshot values fail explicitly.
24. An accepted research-evidence record saves and reloads exactly through a fresh store instance.
25. The research-evidence store uses a separate SQLite file from the historical candle/coverage store.
26. Evidence persistence does not modify historical candle or coverage storage.
27. `ACCEPTED` evidence requires valid dataset, configuration and result fingerprints.
28. `FAILED` and `INCOMPLETE` records cannot persist or reload as `ACCEPTED`.
29. A duplicate evidence ID is rejected without overwriting the existing record.
30. Provenance, optional repository revision, summary and artifact references survive persistence and reload.
31. Deterministic M3.8c validation requires no AngelOne, network, credentials or wall-clock dependency.

Canonical tests must also prove domain/version separation, SHA-256 output form and meaningful distinctions between integer/float, list/tuple, and null/string/Boolean values. Dataset generation must reject noncanonical input without sorting, deduplication, chronology repair or timestamp conversion. Configuration identity uses effective research values and requires risk-per-trade to be supplied explicitly. Stable-result identity covers complete current `Trade`/`BarRecord` content and equity curve while excluding `session_id`; it does not assert financial correctness.

The immutable evidence model contains evidence ID, timezone-aware microsecond-precision creation time, explicit status, `DatasetContext`, requested `TimeRange`, three fingerprints, provenance, optional repository revision, concise summary and artifact references. Evidence ID and creation time are not fingerprint inputs. The logical record contract is authoritative; exact SQL layout and final filename are not frozen. Boundary validation rejects non-datetime creation values, naive creation timestamps, unordered or inappropriate artifact-reference inputs, and non-string artifact entries; ordered lists and tuples normalize to immutable tuples.

Completion evidence:

- Design baseline: `f32848c2`
- Implementation commit: `96382079 Implement M3.8c reproducibility identity and evidence`
- Pre-change full suite: 248 passed
- Final focused M3.8c research suite: 58 passed
- M3.8a regression: 5 passed
- M3.8b regression: 3 passed
- Post-change full suite: 306 passed
- `git diff --check`: passed
- Production files: +527 / -0
- Test files: +639 / -0
- Repository line changes: +1166 / -0
- Real provider/network/credentials: none
- Runtime/M3.8d wiring: none
- Production defects discovered: none

The evidence validates deterministic bytes and fingerprints, domain/version separation, meaningful type distinctions, exact finite-float encoding, explicit unsupported/non-finite rejection, and preservation of supplied datetime representation. Dataset identity reacts to context, request and candle changes while rejecting noncanonical chronology without repair. Configuration identity reacts to effective research values while excluding presentation controls. Stable-result identity excludes `session_id`, reacts to complete Trade, BarRecord and account-state changes, and canonicalizes decision snapshots deterministically.

Evidence validation also covers `ACCEPTED`/`FAILED`/`INCOMPLETE` invariants, exact durable reload through a fresh SQLite store instance, duplicate rejection without overwrite, physical separation from historical storage, and persistence of provenance, repository revision, summary and artifact references. Created-at and artifact-reference boundaries were explicitly hardened and validated.

M3.8c does not wire evidence persistence into `run_backtest()`, HistoricalSource, main, WFA, API or frontend. M3.8d remains responsible for the complete fresh/local repeated-run integration.

### M3.8d — Integration and repeated-run validation

**Status:** DONE / validated at accepted scope

Required evidence:

1. Provider-fresh canonical candles equal warm-local canonical candles.
2. Repeated local retrieval remains identical.
3. Identical canonical data and configuration yield equivalent stable trades and account/equity records.
4. Dataset fingerprints match across equivalent paths.
5. Configuration fingerprints match for equivalent research-relevant settings.
6. Result fingerprints match for equivalent stable results.
7. Changing a research-relevant input changes the appropriate identity or raises an explicit mismatch.
8. Presentation-only changes do not falsely change research identity.
9. Random session IDs do not break parity.
10. Persisted reference evidence reloads into an inspectable record.
11. Failed or incomplete runs do not become accepted evidence.
12. Deterministic validation completes without a real provider or network.

Completion evidence:

- Implementation and validation commit: `f86b1c05609912a15bf4ec87ed7ef1c7e7ef4c10 Validate M3.8d reproducibility integration`
- Parent: `49edbfc0791eab57b0e1357cba4834f55a13d89a`
- Pre-change full suite: 306 passed
- Focused M3.8d: 3 passed
- M3.8a regression: 5 passed
- M3.8b regression: 3 passed
- M3.8c/research regression: 58 passed
- Post-change full suite: 309 passed
- `git diff --check`: passed
- Production changes and defects: none
- Test scope: `tests/runtime/test_research_reproducibility_integration.py`, +445 / -0
- Runtime/main/WFA/API/frontend production wiring: none
- Real provider/network/credentials: none

The deterministic integration evidence satisfies the required matrix. Provider-backed fresh retrieval and new durable `LOCAL_ONLY` or warm `LOCAL_FIRST` instances return identical canonical candles, including repeated fresh-store reads. Equivalent inputs and research configuration produce equal stable trades, `BarRecord` and account/equity state, equity curves, and dataset/configuration/result fingerprints. Deliberately different session IDs and provenance leave the reproducibility identities unchanged.

Accepted evidence round-trips exactly through fresh `SQLiteResearchEvidenceStore` instances in a database physically and logically separate from historical candle/coverage storage. Research-relevant configuration changes are detected, while replay, visualization and export controls do not change configuration identity. Duplicate IDs cannot overwrite accepted evidence. Provider failure creates no false retrieval coverage or false `ACCEPTED` record, and explicit `INCOMPLETE` evidence reloads as `INCOMPLETE`. The configuration fingerprint explicitly uses effective risk `1.0`, matching current Backtest execution for this validated path.

M3.8d validates the complete fresh → persistence → Backtest → fingerprints → evidence → durable-local rerun composition through deterministic tests. It adds no automatic evidence wiring to runtime, main, WFA, API or frontend production paths.

### Evidence policy and boundaries

Deterministic fake/local parity is the authoritative automated evidence and belongs in relevant regression suites when changes affect historical retrieval/persistence, candle or dataset identity, Backtest inputs/results, or fingerprint logic. Real AngelOne/provider fresh-to-local smoke validation is optional supplementary milestone/release evidence because authentication, network, rate limits and provider corrections are external variables. Major validation points retain inspectable reference-run evidence; ordinary unit-test runs need not create permanent evidence records.

M3.8 parity compares stable detailed outputs rather than summary metrics alone. It does not validate Backtest economic correctness, WFA optimization/window/equity validity, paper/live behavior, market-calendar or expected-bar completeness, broker-session lifecycle, or real-money execution. Those remain M4, M5 and later milestone concerns. M3.8a through M3.8d are validated at their accepted scopes, so M3.8 is DONE. Parent M3 closure and any M4 authorization remain separate governance actions.

### M3 parent milestone closure

M3.1 through M3.8 are complete and validated at their individually accepted scopes. Their existing evidence is aggregated for parent closure, so M3 — Offline / Historical Market-Data Foundation is DONE at its accepted scope.

No new validation run was performed for this documentation-only parent closure. The latest accepted full-suite evidence remains 309 passed at `f86b1c0 Validate M3.8d reproducibility integration`, and the M3.8 documentation closure is `d792fae6f4601be3651cf88de6382ae1bb95bc8b`.

This parent status change created no new technical acceptance claim. M4 owns Backtest financial and economic validity, M5 owns WFA validity, and later milestones own real market-data paper operation, paper-session lifecycle, application workflows and V1 release acceptance. At M3 parent closure M4 remained RESERVED and NOT AUTHORIZED; the later M4 design baseline changes its roadmap status to READY without authorizing implementation.

## 9. M4 — Backtest Validity

**Status:** IN_PROGRESS / partially validated through completed M4.2, M4.3, M4.4 and M4.5

M4 requires deterministic evidence that bar-based execution, strategy/execution state, portfolio economics, risk controls, account metrics and reproducibility identity satisfy the accepted AD-011, AD-016 and AD-018 contracts. M4.2 through M4.5 are validated at their accepted scopes.
M4.6–M4.7 remain unvalidated, so M4 remains IN_PROGRESS. The latest accepted full suite is 443 passed in 9.03s at M4.5 implementation `57ccfac`.

### M4.1 — Backtest economic contract

**Status:** DONE at documentation/design-contract scope only

M4.1 freezes the intended completed-bar/next-open, protective-stop, state-authority, sizing, return, drawdown, end-of-data, brokerage and economic-policy-version contracts. No test run was performed for this documentation-only design baseline, and no production behavior is claimed validated.

### M4.2 — Signal/execution state agreement

**Status:** DONE / validated at accepted scope

M4.2 validates the typed, immutable, ordered AD-017 feedback contract through the authoritative execution → Backtest → strategy-runner → strategy-hook boundary. Strategy signals remain intents, and feedback is emitted only after the portfolio/execution outcome is authoritative. The optional BaseStrategy hook remains compatible through a default no-op; `SMACrossOverStrategy` is the validated reference strategy, while PivotBoss remains outside M4.2 validated scope.

Accepted evidence covers:

1. accepted BUY convergence: a BUY intent does not open strategy-local state, and `ENTRY_ACCEPTED` does;
2. rejected BUY convergence: `ENTRY_REJECTED` leaves or returns strategy-local state to flat;
3. strategy SELL convergence: a SELL intent does not close local state before execution, and `STRATEGY_EXIT` does;
4. protective-stop convergence: `PROTECTIVE_EXIT` closes local state after the authoritative forced exit;
5. a machine-readable rejection reason for drawdown-limit, invalid-quantity/entry or portfolio-risk rejection as applicable;
6. feedback is delivered only after the authoritative portfolio outcome and contains symbol, timestamp, resulting authoritative position state, and applicable fill price/quantity/rejection reason;
7. a strategy execution-feedback handler failure propagates and fails the Backtest explicitly;
8. contradictory validated-research states fail explicitly, including BUY while authoritative state is LONG or SELL while authoritative state is FLAT when these indicate disagreement;
9. ordered multiple-event capability without a one-event-per-candle restriction, including infrastructure subsequently exercised by M4.3 for `ENTRY_ACCEPTED` → `PROTECTIVE_EXIT`; and
10. no regression to authoritative PortfolioManager/TradeExecutionEngine accounting or ownership.

Completion evidence:

- Implementation commit: `770d3a5 Implement M4.2 execution feedback contract`
- Focused execution/backtest validation: 26 passed
- Independently rerun full suite: 323 passed in 6.53s
- Previous accepted full-suite baseline: 309 passed
- Tests added: 14
- Repository line changes: +620 / -13, net +607
- Staged `git diff --check`: passed before commit

M4.2 does not validate PivotBoss or paper-runtime feedback integration. M4.3 separately validates next-open execution, gap-stop, event-priority and fill semantics for Backtest.

### M4.3 — Execution timing and stop/fill validity

**Status:** DONE / validated at accepted implementation scope

Accepted evidence exercises the phased Backtest contract with one immutable pending intent carrying decision-time context.

Validated evidence proves:

1. a completed signal-bar decision cannot receive a same-close fill and is executed, if possible, only on the next execution bar;
2. a queued BUY uses the next bar open, while its stop uses only the decision-time rejection midpoint or the existing 2% fallback from the signal-bar close;
3. a queued discretionary SELL uses the next bar open;
4. an ordinary long stop uses the stop price as reference when the bar does not gap through it;
5. a gap-through long stop uses the bar open as reference;
6. BUY or SELL slippage is applied exactly once to the selected reference price;
7. deterministic priority is gap protective stop → queued discretionary SELL → ordinary protective stop, with a gap exit consuming the queued SELL without a second exit;
8. a long entry is rejected with `INVALID_ENTRY` when its decision-time stop is not strictly below the actual post-slippage fill;
9. a position accepted at the next open may be stopped by that same bar's later low, producing ordered `ENTRY_ACCEPTED` → `PROTECTIVE_EXIT` feedback;
10. open-time execution and gap protection occur before any mark to the current close, and only a position remaining open is marked to that close;
11. a decision generated from the final available bar remains pending and unfilled without a synthetic candle or final-close fill;
12. an open final position is retained without automatic liquidation and marked to the final close so final equity includes unrealized P&L;
13. `BarRecord` may report execution from the previous decision and the current completed-bar signal while its singular execution diagnostics represent the final event on a multi-event bar; and
14. M4.2 feedback ordering, state convergence, contradiction detection, handler-failure propagation and authoritative accounting remain green.

Completion evidence:

- Design baseline: `d7ee0d937a99e99154b200936560abc67e32704a Baseline M4.3 execution timing design`
- Implementation commit: `bc9409c904ee77db1c3e587931e4ca8209c4d71d Implement M4.3 execution timing validity`
- Focused Codex validation: 41 passed in 1.09s
- Additional Backtest/execution focused validation: 37 passed in 0.19s
- Independent full regression: 334 passed in 7.88s
- Previous accepted full-suite baseline: 323 passed
- Tests added: 11
- Repository line changes: production +338 / -191; tests +415 / -11; total +753 / -202; documentation +0 / -0

The evidence preserves M4.2 contradiction detection, ordered feedback, handler-failure propagation and authoritative accounting. It also confirms legacy immediate `on_signal()` compatibility for non-Backtest callers; PaperRuntime was not migrated. M4.3 does not validate M4.4/M4.5 metrics, equity-based sizing, affordability, final drawdown policy, M4.6 identity, PivotBoss, paper/live, WFA, API/frontend or release behavior.

### M4.4 — Account returns and performance metrics

**Status:** DONE/CLOSED at accepted implementation/validation scope

Authoritative Backtest reporting uses `PerformanceMetrics.summarize_backtest(result: BacktestResult)` and no longer uses the existing `PerformanceMetrics.summarize(trades)`. The trade-only API remains unchanged as an explicitly legacy compatibility path for current WFA callers. M4.4 did not migrate WFA optimizer scoring, window metrics, capital/configuration propagation, stitching, verdicts or metric keys; WFA account-metric validity remains M5 work.

The implementation preserves instrument price return, gross monetary trade P&L, net monetary trade P&L and account/equity return as distinct measures. `Trade.pnl_pct` retains instrument fill-to-fill return meaning. For a normal non-empty canonical Backtest, starting equity is the first `BarRecord.equity` under the current M4.3 lifecycle and ending equity is the last. Account P&L is ending minus starting equity, and account return percentage is account P&L divided by starting equity and multiplied by 100. This first-record policy is not a universal assumption for future seeded-position or preloaded-state Backtests.

Transaction costs, realized P&L and final unrealized marked P&L participate through authoritative equity. Zero completed trades do not suppress account metrics. Empty no-bar/no-trade results report zero account P&L, account return and drawdown. Trades without equity records fail explicitly as inconsistent. Every equity point on a non-empty curve must be finite, and starting equity must be finite and strictly positive. M4.4 adds no `initial_capital` field to `BacktestResult` and does not modify frozen AD-015 v1.

Maximum equity drawdown evaluates every recorded authoritative equity point. Starting equity is the initial peak; each point updates the peak and contributes `(peak - equity) / peak * 100`; the greatest result is reported as a non-negative loss magnitude. Empty and single-point curves report zero. Recovery does not erase an earlier maximum, unrealized P&L and transaction costs participate through equity, negative equity may produce a result greater than 100% without clipping, and authoritative Backtest drawdown never compounds `Trade.pnl_pct`.

The authoritative metric keys and meanings are:

- `completed_trade_count`: number of completed `Trade` records;
- `net_profitable_trade_count`: completed trades with net monetary `pnl > 0`;
- `net_losing_trade_count`: completed trades with net monetary `pnl < 0`;
- `net_breakeven_trade_count`: completed trades with net monetary `pnl == 0`;
- `net_profitable_trade_rate_pct`: net-profitable completed trades divided by all completed trades, multiplied by 100;
- `mean_positive_instrument_return_pct`: mean `Trade.pnl_pct` among strictly positive instrument returns;
- `mean_negative_instrument_return_pct`: mean `Trade.pnl_pct` among strictly negative instrument returns;
- `mean_instrument_return_pct`: arithmetic mean of all completed `Trade.pnl_pct` values, explicitly not account expectancy;
- `gross_realized_pnl`: sum of completed-trade gross monetary P&L;
- `net_realized_pnl`: sum of completed-trade net monetary P&L;
- `mean_net_pnl_per_completed_trade`: net realized P&L divided by completed-trade count, representing monetary expectancy per completed trade;
- `completed_trade_transaction_cost_total`: sum of transaction costs attached to completed trades, without claiming to include an entry cost belonging to an open terminal position;
- `account_pnl`: ending authoritative equity minus starting authoritative equity;
- `account_return_pct`: account P&L divided by starting authoritative equity, multiplied by 100; and
- `max_equity_drawdown_pct`: greatest authoritative-equity peak-to-subsequent-equity decline.

For zero completed trades, trade counts, rates, means, realized totals and per-trade expectancy are zero, while account metrics remain equity-derived and may be nonzero. Calculations remain full precision programmatically; console/export presentation owns rounding. `avg_win_pct`, `avg_loss_pct`, `expectancy_pct` and synthetic `max_drawdown_pct` must not be presented as authoritative Backtest metrics, although they may remain temporarily inside the legacy WFA compatibility path until M5.

Accepted deterministic evidence proves:

1. `Trade.pnl_pct` remains instrument return;
2. authoritative equity moving from 100000 to 101000 reports +1% account return even when instrument return is +10%;
3. transaction costs affect account return through authoritative equity;
4. maximum drawdown uses authoritative equity rather than compounded trade returns;
5. final unrealized marked equity affects account return and drawdown;
6. unchanged equity with no completed trades reports zero account return and zero drawdown;
7. losing account equity produces negative account return;
8. recovery does not erase historical maximum drawdown;
9. different quantities cannot distort account return through instrument percentages;
10. gross/net/cost monetary semantics remain correct;
11. Backtest reporting uses `summarize_backtest(result)`;
12. legacy WFA behavior is not silently changed; and
13. existing M4.2/M4.3 execution and accounting behavior remains green.

Boundary and expected-failure evidence covers an empty no-bar/no-trade result; non-empty trades with no equity records; non-finite equity; non-positive starting equity; a single-point curve; all-win, all-loss and all-breakeven trade populations; positive instrument return with negative net monetary P&L due to cost; an open terminal position with entry cost; and negative equity producing greater than 100% drawdown.

Completion evidence:

- Design baseline: `259145c0e743156f5b217773fe2b1df34ac93579 Baseline M4.4 account performance design`
- Implementation commit: `7102859ecb80bf932a780825f10634fd36cb0a9d Implement M4.4 account performance metrics`
- Production files: `core/backtest/performance_metrics.py`, `core/backtest/backtest_runner.py`; repository line changes +134 / -3
- Test files: `tests/backtest/test_performance_metrics.py`, `tests/backtest/test_backtest_runner.py`, `tests/walk_forward/test_optimizer.py`, `tests/walk_forward/test_metrics.py`; repository line changes +454 / -0
- Total implementation/test repository line changes: +588 / -3
- `.\.venv\Scripts\python.exe -m pytest tests/backtest/test_performance_metrics.py tests/backtest/test_backtest_runner.py tests/walk_forward/test_optimizer.py tests/walk_forward/test_metrics.py -q`: 32 passed in 0.80s
- `.\.venv\Scripts\python.exe -m pytest tests/backtest/test_backtest_result.py tests/backtest/test_backtest_engine.py tests/backtest/test_execution_timing.py tests/execution/test_execution_feedback.py tests/execution/test_trade_execution_engine.py tests/portfolio/test_portpolio_manager.py -q`: 38 passed in 0.20s
- `.\.venv\Scripts\python.exe -m pytest tests/walk_forward -q`: 8 passed in 0.48s
- `.\.venv\Scripts\python.exe -m pytest tests/runtime/test_historical_runtime_wiring.py tests/runtime/test_historical_source_policy_integration.py tests/runtime/test_backtest_result_parity.py tests/runtime/test_research_reproducibility_integration.py -q`: 29 passed in 1.74s
- Independent full regression: 364 passed in 6.86s, exit code 0
- Previous accepted full-suite baseline: 334 passed; tests added: 30
- Independent `git diff --check`: clean

The implementation leaves `BacktestResult`, `BarRecord` and `Trade` schemas, `TradeBuilder.pnl_pct` semantics and frozen AD-015 v1 unchanged. It adds no M4.5 risk-sizing, affordability or daily/weekly reset behavior; no M4.6 successor identity; and no M5 WFA migration or validity claim.

### M4.5 — Risk sizing and drawdown validity

**Status:** DONE/CLOSED at accepted implementation/validation scope

AD-018 is the validation authority. Accepted evidence proves that Backtest sizing uses authoritative current pre-entry equity, cash affordability includes enabled entry transaction cost, and daily/weekly entry guards use sticky period-start authoritative equity loss rather than peak-to-current drawdown or accumulated trade percentages. The implementation preserves M4.3 no-lookahead ordering and M4.2 feedback/state convergence while leaving M4.4 historical maximum drawdown separate.

The accepted sizing reference is:

~~~text
risk_budget = sizing_equity * risk_per_trade_pct / 100
price_risk_per_share = actual_entry_fill - stop_price
risk_quantity = floor(risk_budget / price_risk_per_share)
max_position_notional = sizing_equity * max_position_pct / 100
max_position_quantity = floor(max_position_notional / actual_entry_fill)
candidate_quantity = min(risk_quantity, max_position_quantity)
~~~

The accepted affordability result is the largest integer quantity `q` no greater than the candidate for which actual-fill notional plus enabled `BrokerageModel` entry cost is no greater than authoritative cash. When brokerage is disabled, only notional participates. `max_position_pct` must be finite and positive but is not restricted to at most 100 because affordability is the final unlevered cash boundary. No affordable share produces `INSUFFICIENT_CASH`; successful entry cannot create negative cash; final accepted entry cost is charged once.

The accepted guard formula is:

~~~text
period_loss_pct = max(
    0,
    (period_start_equity - current_equity)
    / period_start_equity
    * 100
)
~~~

Daily identity is represented candle date and weekly identity is represented `(ISO year, ISO week)`. Baselines use authoritative equity carried before the first observed candle's current-period open-time execution. Exact threshold breaches and latches against new entries for the rest of the period; gains do not raise baselines; recovery does not reopen entries; realized, unrealized and transaction-cost effects enter through equity; exits remain allowed; and no forced liquidation is introduced. Non-positive baseline equity latches without division, non-finite equity fails explicitly and greater-than-100% loss is not clipped. No exchange calendar, timestamp conversion or synthetic session is implied.

#### Accepted deterministic M4.5 evidence

The following 44-case matrix remains the accepted validation contract. The M4.5 implementation and validation evidence was independently reviewed against AD-018 and this contract. The focused M4.5/regression suite passed 193 tests and the independent full regression passed 443 tests; no one-test-per-item mapping is asserted.

##### Position sizing

1. equity 100000, risk 1%, entry 100 and stop 90 produces quantity 100;
2. equity 110000 under the same risk/price inputs produces quantity 110;
3. equity 90000 under the same risk/price inputs produces quantity 90;
4. original capital 100000 with current equity 50000 produces quantity 50, proving original capital no longer controls later sizing;
5. `max_position_pct` caps quantity from current equity rather than original capital;
6. zero or negative equity produces no valid entry quantity;
7. non-finite equity fails explicitly; and
8. missing, equal-entry, above-entry or otherwise invalid long stop is rejected.

##### Available-cash affordability

9. a fully affordable sizing candidate remains unchanged;
10. a sizing candidate exceeding available cash is reduced;
11. enabled brokerage can make otherwise affordable raw notional unaffordable;
12. the largest affordable integer quantity no greater than the candidate is selected;
13. inability to afford one share produces `INSUFFICIENT_CASH` without portfolio mutation;
14. accepted entry cannot produce negative authoritative cash;
15. brokerage-disabled affordability uses notional alone;
16. accepted entry cost is applied exactly once;
17. brokerage cap and component/total rounding boundaries preserve correct affordability selection; and
18. one-share cases immediately below, equal to and above required cash obey the inclusive `required_cash <= available_cash` contract.

##### Daily and weekly equity-loss guards

19. daily loss below threshold permits a new entry;
20. loss exactly equal to the daily threshold blocks entry;
21. loss exactly equal to the weekly threshold blocks entry;
22. a represented new date resets daily baseline/latch while preserving weekly state;
23. a new represented `(ISO year, ISO week)` resets weekly baseline/latch;
24. ISO-year/week identity resets correctly across year boundaries, including sparse observations with equal week numbers in different years;
25. unrealized marked loss alone can breach a guard;
26. entry or exit transaction cost can contribute to breach through authoritative equity;
27. realized loss contributes through authoritative post-close equity;
28. gain followed by decline is measured from period start rather than period peak;
29. a breached period remains latched despite recovery;
30. a carried position uses prior completed/marked authoritative equity at a day/week transition;
31. sparse date/week changes reset at the first observed new identity without synthetic sessions;
32. non-positive period-start equity latches without division;
33. negative equity can produce greater-than-100% period loss without clipping; and
34. simultaneous daily and weekly breach/reset behavior is deterministic.

##### Ordering, configuration and regression

35. current-open sizing cannot observe the current candle high, low or close;
36. a gap-stop after a period transition is measured from the new period's carried-equity baseline;
37. M4.3 next-open, gap/ordinary-stop and same-bar entry/protective-stop behavior remains intact;
38. M4.2 ordered feedback, rejection handling and strategy/execution state agreement remains intact;
39. M4.4 account return and historical maximum equity drawdown remain intact and separate from M4.5 guards;
40. every rejected entry leaves authoritative cash, position, completed trades and transaction-cost accounting unchanged and exposes no stale execution diagnostics;
41. effective `AppConfig.risk_per_trade_pct` reaches canonical Backtest execution through `RuntimeContext`, `BacktestEngine` and `TradeExecutionEngine`;
42. WFA-specific APIs, capital/configuration propagation, scoring, metric keys, stitching and verdicts are not migrated, while inherited shared Backtest changes do not create a WFA validity claim;
43. legacy non-Backtest `on_signal()` compatibility is explicitly assessed without claiming its economics valid or migrating PaperRuntime/live policy; and
44. independent full-suite regression is required before M4.5 implementation closure.

Completion evidence:

- Design baseline: `78e4493430dab2a9389bfda4e41b1149ef038f7f Baseline M4.5 risk sizing design`
- Implementation commit: `57ccface0f086dd12e38fca9cfed3b5aa92fbe9c Implement M4.5 risk sizing and drawdown validity`
- Focused M4.5/regression suite: 193 passed in 3.01s
- Independent full regression: 443 passed in 9.03s, exit code 0
- Previous accepted full-suite baseline: 364 passed; increase: 79 tests
- Repository line changes: production +301 / -38; tests +911 / -1; total +1212 / -39
- Independent `git diff --check`: clean

M4.5 production changes are `core/risk/risk_manager.py`, `core/risk/drawdown_risk_manager.py`, `core/execution/trade_execution_engine.py`, `core/portfolio/portfolio_manager.py`, `core/execution/execution_feedback.py`, `core/runtime/runtime_context.py`, `core/backtest/backtest_engine.py` and `main.py`. `BacktestResult`, `BarRecord`, `Trade`, `Position`, TradeBuilder, BrokerageModel, SlippageModel, StopLossManager, PortfolioRiskManager, PositionBook, BacktestConfig, AppConfig/loaders, BacktestRuntime, PaperRuntime, BrokerExecutionEngine, WFA production, M4.4 metrics and research identity/fingerprint code remain unchanged.

The validated M4.5 scope does not include WFA validity/configuration migration, M4.6 successor identity, M4.7 integration, PaperRuntime or broker/live risk migration, multi-symbol redesign, exchange calendars, exact broker/tax fidelity, leverage/margin/shorts/derivatives, forced liquidation, PivotBoss or obsolete standalone-script repair, or API/frontend behavior. WFA may inherit corrected shared Backtest mechanics, but that is not a WFA validity claim. Frozen AD-015 v1 remains unchanged.

### M4.6 — Research manifest and deterministic references

**Status:** READY at accepted design scope under AD-019 / implementation not validated

M4.6 must implement a complete versioned effective-input manifest, shared Backtest economic policy, successor configuration identity and deterministic references without modifying frozen AD-015 v1 contracts. `kanasu.dataset.v1`, `kanasu.backtest-config.v1`, `kanasu.backtest-result.v1`, canonical serialization v1 and existing ResearchEvidence rows remain valid.

Accepted identity/manifest requirements:

1. Introduce `kanasu.backtest-economics.v1` and one shared `BacktestEconomicPolicy`; execution and manifest identity consume the same accepted fixed values rather than maintaining duplicate defaults.
2. Introduce `kanasu.backtest-run-manifest.v1` linking dataset context/request/fingerprint to effective strategy, initial capital, effective risk, effective `ExecutionConfig` and economic policy.
3. Introduce successor `kanasu.backtest-config.v2` using the existing canonical serializer. Dataset candle content and stable result content remain independent v1 fingerprint domains.
4. Record effective inputs, not merely raw configuration fields. At this design baseline `AppConfig.risk_per_trade_pct` is effective; `AppConfig.initial_capital`, `AppConfig.slippage_pct` and `AppConfig.brokerage_pct` are not canonical `main()` Backtest economic inputs and M4.6 does not silently rewire them.
5. Keep presentation/replay/export controls, journal paths, provider/source provenance, repository revision, artifact locations and session IDs outside configuration identity.
6. Keep `ResearchEvidence` and its SQLite schema backward-compatible. V2 configuration fingerprints fit the existing field, and accepted v2 evidence must reference the manifest through existing artifact references. M4.6 does not require automatic canonical-runtime evidence persistence.
7. Non-finite canonical values and unsupported canonical types fail explicitly under the existing serialization rules.

Primary hand-calculated reference:

~~~text
dataset context:
  symbol: TEST
  timeframe: 15m
  timezone: Asia/Kolkata
request: [2026-01-05 09:15:00+05:30, 2026-01-05 10:15:00+05:30)

effective inputs:
  initial capital: 100000
  risk per trade: 1%
  max position: 20%
  slippage: OFF
  brokerage: OFF
  economic policy: kanasu.backtest-economics.v1

Bar A 09:15
  OHLCV: 100 / 101 / 99 / 100 / 1000
  completed-bar decision: BUY
  rejection midpoint: 90.2

decision stop:
  90.2 × (1 - 0.2%) = 90.0196
  round to 0.05 tick = 90.00

Bar B 09:30
  OHLCV: 100 / 106 / 95 / 105 / 1100
  BUY next-open fill: 100
  risk budget: 100000 × 1% = 1000
  risk/share: 100 - 90 = 10
  risk quantity: 100
  max-position quantity: floor(100000 × 20% / 100) = 200
  accepted quantity: 100
  after Bar B close mark, cash: 90000
  after Bar B close mark, equity: 100500

Bar C 09:45
  OHLCV: 105 / 111 / 104 / 110 / 1200
  completed-bar decision: SELL
  cash: 90000
  equity: 101000

Bar D 10:00
  OHLCV: 110 / 112 / 109 / 111 / 1300
  SELL next-open fill: 110
  quantity: 100
  final cash: 101000
  final equity: 101000

completed trade:
  entry: 100
  exit: 110
  stop: 90
  quantity: 100
  gross P&L: 1000
  transaction cost: 0
  net P&L: 1000
  instrument return: 10%
  account P&L: 1000
  account return: 1%
  maximum equity drawdown: 0%
~~~

Required deterministic evidence must cover:

- identical effective manifests produce identical canonical v2 configuration identity;
- changing strategy parameters, initial capital, effective risk, slippage percentage/enabled state, brokerage-enabled state, policy identifier or any policy scalar changes v2 identity as applicable;
- mapping order and excluded presentation/provenance/repository/session fields do not change configuration identity;
- changes to raw but inert AppConfig fields do not masquerade as effective Backtest changes;
- the primary reference reproduces exact fills, stop, quantity, cash, position/equity sequence, completed trade and metrics above;
- at least one additional hand-calculated enabled-slippage/brokerage reference or equivalent deterministic sensitivity case validates non-zero execution economics;
- manifest/economic-policy values consumed by execution and identity cannot silently diverge;
- existing v1 reproducibility/evidence tests remain valid and persisted v1 records require no destructive migration; and
- M4.2–M4.5 timing, feedback, accounting, metrics, sizing, affordability and period-loss behavior remain regression-safe.

The economic outputs are hand-calculated acceptance references. SHA-256 fingerprints are deterministic canonical-serialization outputs and should be asserted by reproducible tests rather than described as manually calculated hashes. This section records accepted future evidence, not newly executed M4.6 implementation evidence.

### M4.7 — Backtest validity integration

**Status:** PLANNED / not validated

M4 closure requires integrated deterministic reference runs, focused and regression neighborhoods, the full suite, explicit boundary and expected-failure cases, exact evidence reporting, and synchronization of affected authoritative documentation. The integration claim must remain bounded to Backtest validity and must not imply WFA, paper/live, application or V1 release acceptance.

M4 validation does not establish exact brokerage or tax fidelity. M5 owns WFA validity; M6/M7 own real-data paper and paper-session work; M8 owns authoritative API/frontend workflow; and M9 owns V1 release acceptance.

## 10. V1 release gates

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
