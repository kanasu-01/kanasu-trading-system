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

- **M3 — DONE** — Offline / historical market-data foundation.
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
  - **M3.7 — DONE** — Historical source policy/runtime wiring.
    - **M3.7a — DONE** — Historical source policy contract.
    - **M3.7b — DONE** — Broker historical provider adapter.
    - **M3.7c — DONE** — Backtest/WFA runtime wiring and lazy provider construction.
    - **M3.7d — DONE** — Source-policy integration and failure validation.
  - **M3.8 — DONE** — Historical-path parity and reproducibility.
    - **M3.8a — DONE** — Historical input parity.
    - **M3.8b — DONE** — Backtest result parity.
    - **M3.8c — DONE** — Reproducibility identity and research-evidence persistence.
    - **M3.8d — DONE** — Integration and repeated-run validation.

### P2 — Trusted Research Engine

- **M4 — IN_PROGRESS** — Backtest validity.
  - **M4.1 — DONE** — Backtest economic contract at design-contract scope.
  - **M4.2 — DONE** — Signal/execution state agreement at accepted implementation/validation scope.
  - **M4.3 — PLANNED** — Execution timing and stop/fill validity.
  - **M4.4 — PLANNED** — Account returns and performance metrics.
  - **M4.5 — PLANNED** — Risk sizing and drawdown validity.
  - **M4.6 — PLANNED** — Research manifest and deterministic references.
  - **M4.7 — PLANNED** — Backtest validity integration.
- **M5 — RESERVED** — WFA validity.

### P3 — Real-Market-Data Paper Runtime

- **M6 — RESERVED** — Live market-data foundation.
- **M7 — RESERVED** — Paper-session integration.

### P4 — Research and Paper Application

- **M8 — RESERVED** — Research and paper application.

### P5 — V1 Acceptance and Release

- **M9 — RESERVED** — V1 validation and release.

M3.1 through M3.8 are complete at their accepted scopes, so M3 is DONE at its accepted historical-data foundation scope. M4 is IN_PROGRESS following completed M4.2 implementation and validation. M4.1 is complete only at design-contract scope, M4.2 is DONE at its accepted scope, and M4.3–M4.7 remain PLANNED. M5–M9 remain RESERVED proposals.

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

**Status:** DONE.

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

M3.7a–M3.7d are complete at their accepted scopes.

#### M3.7b — Broker historical provider adapter

**Status:** DONE.

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

**Completion evidence:**

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
- `HistoricalFeedProvider` implements the accepted provider shape by composing HistoricalFeed without duplicating chunk logic
- Successful complete, sparse and confirmed-empty retrieval produce explicit full-request coverage
- Request-start inclusion and exact request-end exclusion preserve half-open provider semantics
- Other out-of-range candles, incompatible awareness and failed streams are rejected without clipping, conversion or manufactured coverage
- AngelOne valid empty data now returns an empty list; malformed responses remain errors and non-empty parsing remains unchanged
- BaseBroker, HistoricalFeed, HistoricalSource, AppConfig, main, backtest and WFA runtime remain unchanged
- No expected-bar, session, calendar or gap-inference logic was added

M3.7b added no AppConfig, main, backtest, WFA, broker-factory, login-timing or source-policy runtime wiring. Those runtime changes were completed separately in M3.7c, and their wider integration/failure behavior was validated in M3.7d.

#### M3.7c — Backtest/WFA runtime wiring and lazy provider construction

**Status:** DONE.

**Outcome:** Make backtest and WFA consume canonical historical candles through `HistoricalSource` instead of accepting `BaseBroker`, constructing `HistoricalFeed`, or owning source-selection logic. External provider and broker construction becomes lazy and occurs only when the accepted source policy requires it.

**Runtime dependency direction:**

~~~text
Backtest / WFA
      ↓
HistoricalSource
      ↓
source policy
      ↓
local SQLite store
      ↓ when external access is required
lazy provider factory
      ↓
create authenticated AngelOne broker
      ↓
HistoricalFeed
      ↓
HistoricalFeedProvider
~~~

- `HistoricalSource` remains the sole owner of `LOCAL_ONLY`, `LOCAL_FIRST` and `PROVIDER_BACKED` branching. Backtest, WFA and main do not duplicate policy decisions.
- `run_backtest()` and `run_walk_forward()` receive a HistoricalSource and request candles with `DatasetContext` plus `TimeRange(config.start, config.end)`. HistoricalFeed and BaseBroker leave their runtime dependency paths.
- A small `core/market_data/historical_source_factory.py` composition boundary constructs SQLiteCandleStore eagerly and HistoricalSource with a lazy provider factory.
- Constructing source composition performs no AngelOne environment loading, broker construction or login. Only invocation of the provider factory calls existing `create_angelone_broker(paper_mode=True, enable_historical_api=True)`, then creates HistoricalFeed and HistoricalFeedProvider.
- `create_angelone_broker()` remains eager when called. Its config loading, AngelOne construction and login responsibilities remain unchanged; source policy does not move into the broker factory.
- `AppConfig` owns `historical_source_policy`, `historical_database_path` and `historical_request_delay_sec`. Accepted V1 defaults are `HistoricalSourcePolicy.LOCAL_FIRST`, `data/historical.sqlite3` and the existing request delay.
- Main performs no unconditional broker construction before runtime selection. BACKTEST and WALK_FORWARD compose and receive HistoricalSource; PAPER and LIVE receive no new historical-source or broker behavior in M3.7c.
- Historical request timestamps pass through unchanged. No UTC conversion, localization, offset stripping or silent naive/aware conversion is introduced.
- The default AngelOne-oriented `BACKTEST_CONFIG` uses explicit timezone-aware Asia/Kolkata start/end values consistent with its declared timezone. This does not make DatasetContext timezone an automatic localization rule; user-supplied naive requests remain valid with compatible naive local data and fail explicitly with incompatible aware provider data.
- HistoricalSource, HistoricalFeedProvider, HistoricalFeed, BaseBroker and the AngelOne historical adapter retain their accepted behavior unless a focused RED test proves a defect.

**Validated evidence:**

1. Creating source composition alone loads no AngelOne credentials, constructs no broker and performs no login.
2. `LOCAL_ONLY` with complete local coverage performs zero external construction/login.
3. Fully cached `LOCAL_FIRST` performs zero external construction/login.
4. Missing `LOCAL_FIRST` invokes the lazy provider only after persisted coverage has been examined.
5. `PROVIDER_BACKED` invokes the provider despite complete local coverage.
6. Backtest retrieves through HistoricalSource rather than HistoricalFeed or BaseBroker.
7. WFA retrieves through the same HistoricalSource contract rather than HistoricalFeed or BaseBroker.
8. Backtest and WFA contain no source-policy branching.
9. Main performs no unconditional broker construction/login before runtime selection.
10. External historical provider construction uses `paper_mode=True` and `enable_historical_api=True`.
11. Existing HistoricalSource, HistoricalFeedProvider, HistoricalFeed, AngelOne historical, market-data and broader regression suites remain green.
12. No timestamp normalization is introduced.
13. Request/provider awareness incompatibility remains an explicit failure.

**Completion evidence:**

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
- `.\.venv\Scripts\python.exe`, Python 3.11.9

M3.7c completed the dependency change from broker-backed runtime retrieval to HistoricalSource for both Backtest and WFA. Historical source composition now creates SQLite capability and its parent directory immediately while retaining AngelOne creation, login, HistoricalFeed and HistoricalFeedProvider composition inside one lazy provider closure. `AppConfig` and its environment loader own the accepted policy, database-path and request-delay configuration. Main composes HistoricalSource only after selecting BACKTEST or WALK_FORWARD and adds no historical-source behavior to PAPER or LIVE.

The default AngelOne-oriented BacktestConfig now carries explicit Asia/Kolkata-aware request bounds. No timestamp normalization, runtime localization, offset stripping or automatic awareness conversion was added. HistoricalSource, HistoricalFeedProvider, HistoricalFeed, BaseBroker, AngelOne historical parsing, retrieval validation and SQLite coverage semantics retained their accepted behavior; the broker factory remains source-policy unaware and eager only when invoked.

This evidence validates runtime dependency wiring and lazy construction at M3.7c scope. The wider integration and failure matrix was validated separately in M3.7d.

#### M3.7d — Source-policy integration and failure validation

**Status:** DONE.

**Outcome:** Complete M3.7 by validating the existing historical-source composition and research-runtime path under realistic success and failure conditions, without redesigning its accepted architecture.

**Scope:**

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

End-to-end means this historical-source/research-runtime boundary. It does not include backtest economics, strategy correctness, WFA optimization validity, paper/live trading, UI, or real broker/network operation. Tests remain deterministic and must not contact AngelOne.

**Required evidence:**

1. Both BACKTEST and WALK_FORWARD use pre-populated trusted SQLite data under `LOCAL_ONLY`, deliver canonical candles to the research runtime, and load no credentials, construct no broker, perform no login, and access no provider.
2. Both runtimes use fully covered warm `LOCAL_FIRST` data without credentials, broker construction, login, or provider access. This is mandatory DW-011 resolution evidence.
3. Missing `LOCAL_FIRST` coverage is detected before lazy provider construction; only planned missing ranges are requested; accepted evidence becomes durable coverage; and a later warm retrieval avoids provider access.
4. `PROVIDER_BACKED` requires fresh provider access despite complete local coverage, and completion depends on that provider result's explicit coverage.
5. Missing credentials and provider construction/login failures affect only policies that require external access, fail explicitly without leaking secrets or manufacturing coverage, and preserve accepted local state.
6. Retrieval failure after successful construction creates no coverage for the failing range. Earlier successfully committed provider results remain valid, and retry planning identifies only genuinely missing ranges.
7. Confirmed-empty external results remain explicit durable coverage: warm `LOCAL_FIRST` and later `LOCAL_ONLY` reuse it without external access, while later `PROVIDER_BACKED` still invokes the provider.
8. Persisted/request and request/provider timestamp-awareness incompatibilities fail explicitly without false coverage or timestamp conversion; provider access is avoided when the incompatibility is knowable locally.
9. Backtest and WFA receive equivalent historical-source semantics for the same DatasetContext, TimeRange, policy, local coverage, and provider outcome. Their later trading or research outputs need not be identical.

**Failure semantics:** External construction, authentication, and retrieval failures propagate clearly and create no false coverage. Existing valid local state remains intact. Atomicity remains per accepted provider result: a later failing gap does not roll back earlier accepted gaps, and retries request only actual remaining coverage. Logs and errors must not leak credentials or sensitive data.

**Implementation expectation:** Production-code changes are expected to be none unless focused integration RED evidence proves an implementation defect. Any correction must identify the violated accepted contract, inspect the exact affected file, apply Governance implementation-quality requirements, and remain the smallest coherent fix. This baseline does not authorize a production correction.

**Non-goals:** Real AngelOne/network calls; calendar, holiday, session, expected-bar, or candle-spacing inference; timestamp normalization; destructive provider refresh/replacement; source policy in broker classes; broker-factory redesign; M3.8 parity work; M4/M5 validity work; PAPER/LIVE historical integration; and frontend/API changes.

**Completion evidence:**

- Design baseline: `0726b148`
- Validation implementation: `7f968843 Validate M3.7d source-policy integration`
- Focused M3.7d: 17 passed
- Regression neighborhood: 71 passed
- All market-data: 147 passed
- Runtime / Backtest / WFA: 39 passed
- Full suite: 240 passed
- `git diff --check`: passed
- Production corrections: none

This evidence validates the accepted M3.7d matrix through the actual research-runtime/source-composition boundary. M3.7a–M3.7d are complete at their accepted scopes, so M3.7 is DONE. DW-011 is resolved at the M3.7 integration scope. M3.8 remains a separate RESERVED milestone.

### M3.8 — Historical-path parity and reproducibility

**Status:** IN_PROGRESS.

**Outcome:** Equivalent accepted historical data, used with the same research-relevant configuration, produces equivalent canonical historical input and deterministic stable Backtest output regardless of whether the data arrived through a provider-fresh path or an already persisted local-store path. M3.8 also establishes inspectable deterministic identity for the dataset, research-relevant configuration and stable result.

This milestone proves reproducibility and path parity. It does not establish Backtest economic validity or WFA validity, which remain M4 and M5 responsibilities.

**Current architectural fact:** Provider-fresh retrieval and `LOCAL_FIRST` missing-range retrieval persist accepted candles and coverage into SQLite, then reload canonical local candles before a research runtime consumes them. `LOCAL_ONLY` and fully warm `LOCAL_FIRST` load canonical candles directly from the same local store. M3.8 validates that these accepted paths converge; it must not redesign the historical-source architecture unless focused RED evidence proves a defect.

#### M3.8a — Historical input parity

**Status:** DONE.

**Outcome:** Prove that provider-fresh and local-store paths yield exactly equivalent canonical candles when their accepted underlying market data is equivalent.

Required parity covers candle count, chronological order, timestamps, OHLCV values, `DatasetContext`, requested half-open `TimeRange` semantics and confirmed-empty behavior where applicable. Deterministic automated tests use fake/provider evidence and make no real AngelOne or network call. Source provenance may differ while canonical candle content remains equal.

**Completion evidence:**

- Design baseline: `c53c640`
- Implementation and validation commit: `0a8410ff Validate M3.8a historical input parity`
- Pre-change full suite: 240 passed
- Focused M3.8a: 5 passed
- Source-policy regression: 33 passed
- All market-data: 152 passed
- Post-change full suite: 245 passed
- `git diff --check`: passed
- Production corrections: none
- Test scope: `tests/market_data/test_historical_input_parity.py`, +247 / -0

The evidence proves durable provider-fresh parity through both `LOCAL_ONLY` and warm `LOCAL_FIRST`, including candle count, chronology, timestamp representation, OHLCV values, half-open request boundaries, confirmed-empty evidence and `DatasetContext` isolation. Deterministic validation required no AngelOne, network or credentials. M3.8a completion does not validate Backtest-result parity, fingerprints/evidence persistence or full M3.8 integration.

#### M3.8b — Backtest result parity

**Status:** DONE.

**Outcome:** Given the same canonical candles and research-relevant configuration, provider-fresh and warm-local runs produce equivalent stable Backtest outcomes.

Parity compares detailed stable result content where applicable: completed trades; entry and exit timestamps, direction, prices, quantity and exit reason; gross/net P&L and transaction costs; stable bar-level strategy/execution events; execution prices and quantities; cash, equity, position size and drawdown; and the canonical equity curve. `BacktestResult.session_id` is excluded because it identifies an execution instance and may legitimately differ. Any other excluded nondeterministic field must be explicitly justified and documented. Derived summary equality is supporting evidence and is not sufficient by itself.

**Completion evidence:**

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

The accepted evidence proves exact equality of complete `Trade` records, `BarRecord` sequences and canonical equity curves across provider-backed fresh to `LOCAL_ONLY`, provider-backed fresh to warm `LOCAL_FIRST`, and cold to warm `LOCAL_FIRST` Backtests. Strategy/execution events, execution prices and quantities, cash, equity, position size and drawdown are included. Deliberately different random `session_id` values demonstrate that execution-instance identity is excluded while stable research results remain exactly equal. This does not establish financial correctness of Backtest economics, timing, fills, stops, slippage, brokerage or account metrics, and it does not validate M3.8c or M3.8d.

#### M3.8c — Reproducibility identity and research-evidence persistence

**Status:** DONE.

**Outcome:** Establish deterministic identities for research inputs and stable output, together with a dedicated persistence boundary for inspectable reproducibility evidence.

The accepted AD-015 design, which refines AD-014, is implemented and validated at the reusable M3.8c scope.

**Canonical serialization v1:** Three independent SHA-256 domains carry explicit versioned schema identifiers for dataset, Backtest research-configuration and stable-result identity. Fingerprints use the self-describing `sha256:<64 lowercase hexadecimal characters>` form. Canonical values are type-tagged and preserve distinctions among `None`, Boolean, integer, finite float, string, datetime, list, tuple and mappings with sorted string keys. Floats use exact `float.hex()` representation; datetimes use microsecond-precision ISO form without timezone normalization. Unsupported values and non-finite floats fail explicitly. Tagged values are serialized as deterministic UTF-8 JSON before hashing; Python `hash()`, `repr()`, object identity and arbitrary string fallback are prohibited.

**Dataset fingerprint:** Include `DatasetContext`, requested half-open `TimeRange` and canonical ordered candle timestamps/OHLCV. Do not sort, deduplicate, repair or normalize noncanonical input. Source policy and provider provenance remain separate, so equivalent provider-backed, `LOCAL_FIRST` and `LOCAL_ONLY` canonical data has one dataset identity.

**Research-configuration fingerprint:** Include effective result-affecting inputs: dataset/request identity, strategy name and parameters, initial capital, explicitly supplied effective risk-per-trade percentage, slippage percentage and enablement, brokerage enablement and any other proven result input. Exclude replay/display, visualization, export controls/destinations, UI state, session IDs, journal paths and source provenance. Mapping insertion order must not affect identity.

**Stable-result fingerprint:** Include complete current `Trade` and `BarRecord` content plus canonical equity curve, including recursively canonicalized decision snapshots. Exclude `BacktestResult.session_id`; unsupported snapshot values fail explicitly. This identifies the current deterministic result contract and does not establish financial correctness.

**Research evidence:** An immutable record carries evidence ID, timezone-aware microsecond-precision creation time, status, context/request identity, all three fingerprints, provenance, optional repository revision, concise summary and artifact references. Status is `ACCEPTED`, `FAILED` or `INCOMPLETE`; accepted records require all three fingerprints, while failed/incomplete records cannot masquerade as accepted. Evidence ID and creation time are not fingerprint inputs.

The dedicated SQLite evidence store remains logically and physically separate from the historical candle/coverage SQLite store. It supports save, load by evidence ID, exact round trip and durable fresh-instance reload. Duplicate IDs fail without overwrite, and invalid accepted records fail before persistence. Detailed trades, bars and curves may remain referenced artifacts; the SQL layout and final filename remain implementation details.

Implemented ownership is `core/research/reproducibility.py`, `core/research/models/research_evidence.py` and `core/research/sqlite_research_evidence_store.py`. The placeholder `research_session.py` and existing `ResearchRequest`/`ResearchResult` were not repurposed. M3.8c added no runtime wiring; M3.8d owns the future end-to-end provider-fresh → Backtest → fingerprints → evidence persistence → durable-local rerun proof.

Completion evidence:

- Design baseline: `f32848c2`
- Implementation commit: `96382079 Implement M3.8c reproducibility identity and evidence`
- Full suite: 248 passed before implementation → 306 passed after implementation
- Final focused M3.8c research suite: 58 passed
- M3.8a regression: 5 passed
- M3.8b regression: 3 passed
- `git diff --check`: passed
- Production files: +527 / -0
- Test files: +639 / -0
- Repository line changes: +1166 / -0
- Production defects discovered: none
- Runtime/M3.8d integration: none

The accepted evidence covers deterministic type-tagged serialization, versioned domain-separated SHA-256 identities, strict dataset chronology, effective research-configuration identity, stable Backtest-result identity excluding `session_id`, immutable evidence statuses, and dedicated SQLite evidence persistence with duplicate protection and durable exact reload. Timestamp and artifact-reference boundaries fail explicitly. Validation required no AngelOne, network or credentials. M3.8c does not establish Backtest economic validity.

**Non-goals:** Backtest economic/timing/fill/stop correctness, brokerage tax fidelity, WFA validity, paper/live behavior, final research catalog, analytics warehouse, UI/API workflow, broker-session lifecycle, market-calendar/expected-bar completeness and real-money execution.

#### M3.8d — Integration and repeated-run validation

**Status:** DONE.

**Outcome:** Prove the complete accepted M3.8 contract together.

The accepted deterministic integration evidence completes the bounded M3.8 parity and reproducibility contract without adding automatic production runtime wiring.

Required evidence:

1. Provider-fresh canonical candles equal warm-local canonical candles.
2. Repeated local retrieval remains identical.
3. Identical canonical data and research configuration produce equivalent stable Backtest trades and account/equity records.
4. The dataset fingerprint remains identical across equivalent source paths.
5. The configuration fingerprint remains identical for equivalent research-relevant settings.
6. The result fingerprint remains identical for equivalent stable results.
7. Changing a research-relevant input changes the appropriate identity or produces an explicit mismatch.
8. Changing presentation-only settings does not falsely change research identity.
9. Random session IDs do not break parity.
10. Persisted reference evidence can be reloaded and inspected.
11. Failed or incomplete runs are not falsely recorded as accepted reproducible evidence.
12. Deterministic automated validation requires no real provider or network.

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

Provider-backed deterministic fresh retrieval persists accepted candles and coverage, and fresh durable `LOCAL_ONLY` and warm `LOCAL_FIRST` instances reproduce the same canonical input. Equivalent inputs and research configuration produce identical stable trades, `BarRecord` and account/equity state, equity curves, and all three fingerprints despite different session IDs and provenance. Accepted evidence reloads exactly from the separate evidence SQLite store, duplicate IDs cannot overwrite it, and repeated local retrieval remains identical.

Research-relevant configuration changes alter identity while replay, visualization and export controls do not. Provider failure creates no false retrieval coverage or false `ACCEPTED` evidence, and explicit `INCOMPLETE` evidence reloads with its true status. The configuration fingerprint supplies effective risk `1.0`, matching current Backtest execution for this validated path.

M3.8a through M3.8d are complete at their accepted scopes; therefore M3.8 is DONE. This completion did not itself establish Backtest financial or economic validity, authorize M4, or close parent M3; those remained separate governance actions.

**Validation policy:** Deterministic fake/local parity tests are authoritative automated evidence and run with relevant regressions whenever changes can affect historical retrieval or persistence, canonical candle serialization/identity, dataset identity, Backtest runtime input, strategy/execution result determinism, or fingerprint logic. Major milestone/release validation retains inspectable reference-run evidence. An occasional controlled real-provider fresh-to-local rerun comparison is supplementary because authentication, network behavior, rate limits and provider-side corrections are external variables. Permanent evidence need not be written for every ordinary unit-test execution. Reproducibility and parity remain a mandatory V1 release gate.

**Scope boundary:** M3.8 includes historical source-path and canonical-candle parity, stable Backtest-result parity, deterministic dataset/configuration/result fingerprints, minimal research-evidence persistence, repeat-run validation and a supplementary real-provider smoke policy. It does not establish Backtest timing/fill/stop economics, final account-return semantics, M4 strategy/execution corrections, M5 WFA validity, paper/live validity, DW-015 broker-session lifecycle, UI/API workflow, a complete analytics database, calendar/expected-bar completeness or real-money execution. WFA may support canonical-input delivery evidence only; full WFA result parity and validity remain M5 work.

## Remaining V1 milestones

### M4 — Backtest validity

**Status:** IN_PROGRESS through completed M4.2 implementation and validation.

**Outcome:** Establish deterministic and economically coherent bar-based Backtest semantics, authoritative strategy/execution state agreement, account-based reporting and risk controls, versioned research identity for the new economic policy, and integrated reference evidence.

**Scope boundary:** M4 owns Backtest validity. It does not establish WFA validity, real market-data paper ingestion, paper-session operation, API/frontend authority, V1 release readiness, real-money execution, exact broker/product/tax fidelity, multi-symbol portfolio validity, or market-calendar/expected-bar completeness.

#### M4.1 — Backtest economic contract

**Status:** DONE at accepted design-contract scope. This is a target contract, not evidence that current production behavior satisfies it.

The accepted target is:

1. A strategy decision made from completed bar N cannot execute retrospectively on bar N. A queued market-style BUY or discretionary SELL may execute no earlier than bar N+1 open. Without a next candle, it remains unfilled; the engine does not manufacture an end-of-data execution.
2. A queued long BUY uses the next candle open as its reference. BUY slippage, when enabled, is applied exactly once. The protective stop must be strictly below the actual fill or the entry is rejected explicitly. Once accepted at the open, the position exists for that candle and may be stopped by its later low.
3. For an existing long, `candle.open <= stop_price` uses the candle open as the gap-through-stop reference. Otherwise `candle.low <= stop_price` uses the stop as the ordinary-stop reference. SELL slippage, when enabled, is applied exactly once to the chosen reference.
4. At a new candle open, a protective gap stop has priority over a queued discretionary SELL. Otherwise the queued SELL executes at the open. If the position remains open, ordinary intrabar stop evaluation may then use the candle low.
5. Execution and portfolio state are authoritative. A BUY signal alone does not prove acceptance. The state-agreement contract must report accepted entry, rejected entry, strategy exit and forced/protective exit so strategy-local state converges with the portfolio.
6. Position risk uses current pre-entry account equity. Quantity must also be affordable from available cash including applicable entry transaction cost, and accepted sizing must not create negative authoritative cash.
7. Instrument price return, gross monetary trade P&L, net monetary trade P&L and account/equity return remain distinct. `Trade.pnl_pct` retains instrument-price-return meaning unless explicitly migrated and is not authoritative account return.
8. Authoritative drawdown and performance derive from the account equity curve rather than synthetic compounding of `Trade.pnl_pct`. Daily/weekly equity-risk treatment, including unrealized P&L and session/reset semantics, belongs to M4.5.
9. End of data does not imply a SELL. An open position remains open, is marked to the final available close, and contributes unrealized P&L to final equity. Forced end liquidation requires an explicit configured research policy.
10. The configured simplified `BrokerageModel` is applied exactly once where applicable, can be enabled or disabled, and flows consistently into cash, trade P&L and equity. M4 does not assert exact AngelOne, NSE, product or tax fidelity.
11. AD-015 and `kanasu.backtest-config.v1` remain frozen. M4.6 must introduce a versioned successor research-configuration identity containing an explicit Backtest economic/execution policy version and every effective M4 result-affecting setting. This baseline does not freeze the successor schema identifier.

#### M4.2 — Signal/execution state agreement

**Status:** DONE at accepted implementation/validation scope.

Strategy signals are intents rather than proof of execution. `TradeExecutionEngine` and `PortfolioManager` own authoritative position truth, and strategy-local belief changes only after authoritative execution feedback.

M4.2 implements a typed, immutable feedback contract that supports an ordered sequence of events. Its event types are `ENTRY_ACCEPTED`, `ENTRY_REJECTED`, `STRATEGY_EXIT` and `PROTECTIVE_EXIT`. Each event carries its type, symbol, timestamp, authoritative position state after the event, and applicable fill price, quantity or machine-readable rejection reason. Current rejection classes include drawdown-limit, invalid-quantity or invalid-entry conditions, and portfolio-risk rejection. M4.3/M4.5 may extend the same contract for later accepted reasons such as invalid post-gap stop or insufficient cash; those later semantics remain outside M4.2.

The target feedback flow is:

~~~text
TradeExecutionEngine
    → BacktestEngine
        → StrategyRunner
            → optional BaseStrategy execution-feedback hook
~~~

The strategy hook defaults to a no-op for compatibility. `TradeExecutionEngine` does not mutate strategy-local state directly. Feedback handling failure makes the Backtest fail explicitly rather than allowing potentially divergent strategy and portfolio state.

`SMACrossOverStrategy` is the M4.2 reference strategy. Emitting BUY does not open its local position; `ENTRY_ACCEPTED` opens it and `ENTRY_REJECTED` leaves or sets it flat. Emitting SELL does not close it before execution; `STRATEGY_EXIT` and `PROTECTIVE_EXIT` close it. Contradictory validated-research states, including BUY while authoritative state is LONG or SELL while authoritative state is FLAT, fail explicitly when they represent state disagreement.

The contract is ordered and does not impose a one-event-per-candle limit. It supports a future M4.3 sequence such as `ENTRY_ACCEPTED` followed by `PROTECTIVE_EXIT` on the same bar. PivotBoss remains unvalidated and outside the M4.2 reference-strategy scope.

**Completion evidence:** implementation commit `770d3a5`; focused execution/backtest validation 26 passed; independently rerun full suite 323 passed in 6.53s; 14 tests added over the previous 309-test baseline; repository line changes +620 / -13, net +607; staged diff-check passed before commit.

M4.2 preserves PortfolioManager/execution accounting ownership and leaves M4.3 next-open timing and stop/fill semantics unchanged.

#### Child-step responsibilities

- **M4.2 — Signal/execution state agreement:** DONE at accepted implementation/validation scope under AD-017.
- **M4.3 — Execution timing and stop/fill validity:** implement and validate next-open action timing, ordinary and gap stops, single slippage application, event priority, entry-stop validity and end-of-data behavior.
- **M4.4 — Account returns and performance metrics:** preserve instrument-return meaning while deriving account return, drawdown and performance from authoritative portfolio/equity state.
- **M4.5 — Risk sizing and drawdown validity:** use current pre-entry equity, enforce transaction-cost-aware affordability, and define daily/weekly equity-risk and session/reset semantics.
- **M4.6 — Research manifest and deterministic references:** define hand-calculated reference scenarios, a complete effective run manifest and a versioned successor economic-policy identity without changing AD-015 v1.
- **M4.7 — Backtest validity integration:** validate the complete accepted M4 contract with deterministic reference, boundary, failure, regression and full-suite evidence before milestone closure.

**Dependencies:** M4 builds on M1/M2 authoritative simulated accounting and the completed M3 historical/reproducibility foundation. AD-011 and AD-016 govern its return and economic semantics. Open or partially resolved deferred items DW-001, DW-002 and DW-009 retain their stated M4 ownership.

**Validation direction:** Use deterministic, hand-calculated scenarios and risk-proportionate success, boundary, failure and regression tests. Compare authoritative executions, cash, positions, equity, trade results, drawdown and versioned research identity. The latest accepted full suite is 323 passed at `770d3a5`; M4.1 remains documentation/design evidence only.

**Non-goals:** WFA validity (M5), live data and paper runtime (M6/M7), authoritative application workflows (M8), V1 release acceptance (M9), real-money execution (V2), exact brokerage/tax fidelity, multi-symbol portfolio semantics and calendar-derived completeness.

M4 is IN_PROGRESS and is not complete. M4.3 remains PLANNED and is not authorized automatically; it requires a separate design/authorization step.

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
