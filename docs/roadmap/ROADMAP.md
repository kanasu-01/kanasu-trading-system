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
  - **M4.3 — DONE** — Execution timing and stop/fill validity at accepted implementation/validation scope.
  - **M4.4 — DONE** — Account returns and performance metrics at accepted implementation/validation scope.
  - **M4.5 — DONE/CLOSED** — Risk sizing and drawdown validity at accepted implementation/validation scope.
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

M3.1 through M3.8 are complete at their accepted scopes, so M3 is DONE at its accepted historical-data foundation scope. M4 is IN_PROGRESS following completed M4.2 through M4.5 implementation and validation. M4.1 is complete only at design-contract scope, M4.2–M4.5 are DONE at their accepted scopes, and M4.6–M4.7 remain PLANNED. M5–M9 remain RESERVED proposals.

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

**Status:** IN_PROGRESS through completed M4.2, M4.3 and M4.4 implementation and validation.

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

M4.2 implements a typed, immutable feedback contract that supports an ordered sequence of events. Its event types are `ENTRY_ACCEPTED`, `ENTRY_REJECTED`, `STRATEGY_EXIT` and `PROTECTIVE_EXIT`. Each event carries its type, symbol, timestamp, authoritative position state after the event, and applicable fill price, quantity or machine-readable rejection reason. Implemented rejection classes include drawdown-limit, invalid-quantity or invalid-entry conditions, portfolio-risk rejection and the M4.5/AD-018 `INSUFFICIENT_CASH` extension without changing M4.2 ownership.

The target feedback flow is:

~~~text
TradeExecutionEngine
    → BacktestEngine
        → StrategyRunner
            → optional BaseStrategy execution-feedback hook
~~~

The strategy hook defaults to a no-op for compatibility. `TradeExecutionEngine` does not mutate strategy-local state directly. Feedback handling failure makes the Backtest fail explicitly rather than allowing potentially divergent strategy and portfolio state.

`SMACrossOverStrategy` is the M4.2 reference strategy. Emitting BUY does not open its local position; `ENTRY_ACCEPTED` opens it and `ENTRY_REJECTED` leaves or sets it flat. Emitting SELL does not close it before execution; `STRATEGY_EXIT` and `PROTECTIVE_EXIT` close it. Contradictory validated-research states, including BUY while authoritative state is LONG or SELL while authoritative state is FLAT, fail explicitly when they represent state disagreement.

The contract is ordered and does not impose a one-event-per-candle limit. Completed M4.3 uses it for `ENTRY_ACCEPTED` followed by `PROTECTIVE_EXIT` on the same execution bar. PivotBoss remains unvalidated and outside the M4.2 reference-strategy scope.

**Completion evidence:** implementation commit `770d3a5`; focused execution/backtest validation 26 passed; independently rerun full suite 323 passed in 6.53s; 14 tests added over the previous 309-test baseline; repository line changes +620 / -13, net +607; staged diff-check passed before commit.

M4.2 preserves PortfolioManager/execution accounting ownership. M4.3 subsequently changed Backtest timing and stop/fill semantics without moving that authority.

#### M4.3 — Execution timing and stop/fill validity

**Status:** DONE at accepted implementation/validation scope.

Backtest orchestration owns one pending BUY or discretionary SELL intent between completed bars. The intent retains decision-time context, including the strategy rejection midpoint or fallback signal-bar close needed for stop construction, and executes no earlier than the next candle.

For each candle, pending open-time execution and protective logic run before strategy evaluation. Resulting ordered feedback is delivered before any remaining open position is marked to the current close. StrategyRunner then consumes the completed candle and its decision becomes the next pending intent. A bar record may therefore contain execution from the previous bar's decision and a new signal from the current bar without lookahead.

A queued BUY uses the next open with BUY slippage exactly once. Its decision-time stop must be strictly below the actual fill or the entry is rejected as `INVALID_ENTRY`. After acceptance, the same execution bar may trigger an ordinary protective stop at the stop reference with SELL slippage once, producing `ENTRY_ACCEPTED` → `PROTECTIVE_EXIT`.

For an existing long, priority is gap protective stop at the candle open, then queued SELL at the open, then ordinary intrabar stop at the stop price. A gap exit consumes any queued SELL without a second close. M4.2 contradictory-state validation remains in force, and ordered feedback remains authoritative when multiple events occur; singular execution fields remain final-event diagnostics.

A final-bar decision remains pending and unfilled. No final-close execution or automatic liquidation is manufactured; any position still open after final-bar execution/protection is marked to the final close. M4.3 does not own equity-based sizing, affordability, final drawdown policy, performance metrics, successor identity, PivotBoss, paper/live, WFA, application or release work.

**Completion evidence:** design baseline `d7ee0d9`; implementation commit `bc9409c`; focused validation 41 passed in 1.09s; additional Backtest/execution validation 37 passed in 0.19s; independently rerun full suite 334 passed in 7.88s; 11 tests added over the previous 323-test baseline; repository line changes +753 / -202 across implementation and tests, with no documentation changes in the implementation commit.

The accepted behavior is implemented for Backtest. The legacy immediate `on_signal()` path remains for non-Backtest callers, PaperRuntime was not migrated, and this completion does not validate PivotBoss, M4.4+ economics, WFA or later runtime/application scopes.

#### M4.4 — Account returns and performance metrics

**Status:** DONE/CLOSED at accepted implementation/validation scope.

Authoritative Backtest reporting now uses `PerformanceMetrics.summarize_backtest(result: BacktestResult)`. The existing `PerformanceMetrics.summarize(trades)` remains unchanged as an explicitly legacy trade-only compatibility path for current WFA callers. M4.4 did not redesign WFA optimizer scoring, window metrics, capital/configuration propagation, stitching, verdicts or keys; their migration and validity remain M5 work.

The accepted metric design preserves instrument price return, gross monetary trade P&L, net monetary trade P&L and account/equity return as distinct concepts. `Trade.pnl_pct` remains instrument-price return. For a normal non-empty canonical Backtest, starting equity is the first `BarRecord.equity` under the current M4.3 lifecycle, ending equity is the last, account P&L is ending minus starting equity, and account return percentage is account P&L divided by starting equity and multiplied by 100. The first-record rule does not generalize automatically to future seeded-position or preloaded-state Backtests.

Transaction costs, realized P&L and final unrealized marked P&L participate through authoritative equity. Zero completed trades do not suppress account metrics. Empty no-bar/no-trade results report zero account P&L, return and drawdown; trades without equity records fail as inconsistent; a non-empty curve requires finite equity points and finite, strictly positive starting equity. M4.4 adds no `initial_capital` field to `BacktestResult` and does not change AD-015 v1.

Maximum equity drawdown examines every recorded equity point from an initial peak equal to starting equity and reports the greatest `(peak - equity) / peak * 100` as a non-negative magnitude. Empty and single-point curves report zero, recovery preserves the historical maximum, negative equity may produce more than 100% drawdown without clipping, and authoritative Backtest drawdown never compounds trade percentages.

The authoritative names are `completed_trade_count`, `net_profitable_trade_count`, `net_losing_trade_count`, `net_breakeven_trade_count`, `net_profitable_trade_rate_pct`, `mean_positive_instrument_return_pct`, `mean_negative_instrument_return_pct`, `mean_instrument_return_pct`, `gross_realized_pnl`, `net_realized_pnl`, `mean_net_pnl_per_completed_trade`, `completed_trade_transaction_cost_total`, `account_pnl`, `account_return_pct` and `max_equity_drawdown_pct`. Mean instrument return is not account expectancy; mean net P&L per completed trade is monetary expectancy. Zero-trade trade statistics are zero while account metrics still derive from equity. Programmatic calculations remain full precision and presentation owns rounding. Ambiguous `avg_win_pct`, `avg_loss_pct`, `expectancy_pct` and synthetic `max_drawdown_pct` remain, if needed, only in the temporary WFA compatibility path.

**Completion evidence:** design baseline `259145c0e743156f5b217773fe2b1df34ac93579`; implementation commit `7102859ecb80bf932a780825f10634fd36cb0a9d`; focused validation 32 M4.4/reporting/WFA-compatibility tests, 38 Backtest/execution/portfolio regressions, all 8 WFA tests and 29 runtime/parity/reproducibility tests passed; independent full suite 364 passed in 6.86s with exit code 0; 30 tests added over the previous 334-test baseline; implementation/test repository line changes +588 / -3, comprising production +134 / -3 and tests +454 / -0; independent `git diff --check` clean.

The accepted evidence covers the authoritative 15-key result contract, instrument/account separation, equity-derived account P&L and return, equity-derived historical maximum drawdown, transaction costs, final unrealized equity, zero-trade and open-position behavior, explicit invalid-equity/result failures, unrounded programmatic values, console presentation and unchanged WFA production compatibility. `BacktestResult`, `BarRecord` and `Trade` schemas, `TradeBuilder.pnl_pct` semantics and AD-015 v1 remain unchanged. No M4.5, M4.6 or M5 implementation occurred.

#### M4.5 — Risk sizing and drawdown validity

**Status:** DONE/CLOSED at accepted implementation/validation scope.

AD-018 defines the implemented contract. A Backtest long entry uses authoritative current pre-entry `PortfolioManager` equity. Risk budget is current equity multiplied by `risk_per_trade_pct`; price risk per share is actual next-open BUY fill after configured slippage minus the prior-decision stop; and the risk quantity is capped by max-position notional calculated from the same current equity. Current candle high, low and close cannot influence open-time sizing. Equity, prices and risk inputs are validated; the long stop must be strictly below actual fill; zero/negative equity or quantity below one cannot produce an entry. `max_position_pct` must be finite and positive but is not capped at 100 by configuration because authoritative cash affordability is the final unlevered safety boundary.

Risk/max-position sizing and affordability are separate constraints. For quantity `q`, required cash is actual fill notional plus the current `BrokerageModel` entry cost when brokerage is enabled, otherwise notional alone. M4.5 chooses the largest affordable integer quantity no greater than the sizing candidate. Search-time cost calculations are pure; only final accepted entry cost is charged once. If no share is affordable, execution rejects with `INSUFFICIENT_CASH` without mutating portfolio or cost state. `PortfolioManager` defensively rejects any unaffordable long entry, and accepted entry cannot make authoritative cash negative.

Daily and weekly entry guards use period-start authoritative equity, not period peak-to-current drawdown. Period loss is `max(0, (period_start_equity - current_equity) / period_start_equity * 100)`. Gains do not raise baselines; realized P&L, unrealized marked P&L and transaction costs participate through equity; exact-threshold breach blocks new entries and latches for the rest of that period. Exits and protective stops remain allowed and no forced liquidation is introduced. A new represented candle date resets only the daily baseline/latch; a new `(ISO year, ISO week)` resets weekly state; non-positive period-start equity latches without division; negative equity may produce more than 100% loss without clipping; non-finite observed equity fails explicitly. M4.4 historical maximum equity drawdown remains a separate reporting concept.

M4.5 uses candle-calendar boundaries from the timestamp representation supplied by canonical candles. It does not localize timestamps, alter `DatasetContext` timezone semantics, infer holidays, create missing sessions or introduce an exchange calendar. Sparse data transitions on the first observed new identity. A carried position's new baseline is the authoritative equity from the prior completed/marked bar before current-period open-time execution, so a subsequent gap-stop effect belongs to the new period.

M4.3 ordering remains authoritative. Period transitions first use only timestamp and carried equity. A pending BUY then respects existing latches, derives actual open fill, validates prior-decision stop, samples pre-entry equity/cash, sizes and enforces affordability. Equity is observed after authoritative entry, exit or close-mark mutation; trade percentages are not separately accumulated. Strategy evaluation occurs only after surviving positions are marked to close and risk state is observed. `AppConfig.risk_per_trade_pct` propagates through an effective `RuntimeContext` setting to `BacktestEngine` and `TradeExecutionEngine`, with a compatible 1% default and no duplicate `BacktestConfig` field.

The implementation adds `INSUFFICIENT_CASH`; retains `INVALID_ENTRY`, `INVALID_QUANTITY`, `DRAWDOWN_LIMIT` and `PORTFOLIO_RISK_LIMIT`; treats non-finite authoritative equity, cash, fill or cost as invariant failure; and makes rejected attempts preserve portfolio/accounting state while clearing stale execution diagnostics including `last_transaction_cost`. Production changes were limited to `core/risk/risk_manager.py`, `core/risk/drawdown_risk_manager.py`, `core/execution/trade_execution_engine.py`, `core/portfolio/portfolio_manager.py`, `core/execution/execution_feedback.py`, `core/runtime/runtime_context.py`, `core/backtest/backtest_engine.py` and `main.py`.

M4.5 does not migrate WFA-specific risk/configuration, metrics, scoring, stitching or verdicts; WFA may inherit corrected shared Backtest mechanics without becoming economically validated. It does not change AD-015 v1, create the M4.6 successor identity, migrate PaperRuntime or broker/live policy, redesign multi-symbol risk, introduce exchange calendars, leverage/margin/shorts/derivatives, force liquidation, repair PivotBoss/standalone scripts, or change API/frontend behavior.

**Completion evidence:** design baseline `78e4493430dab2a9389bfda4e41b1149ef038f7f Baseline M4.5 risk sizing design`; implementation commit `57ccface0f086dd12e38fca9cfed3b5aa92fbe9c Implement M4.5 risk sizing and drawdown validity`; focused M4.5/regression suite 193 passed in 3.01s; independent full regression 443 passed in 9.03s with exit code 0; 79-test increase over the previous accepted 364-test baseline; implementation/test repository line changes +1212 / -39, comprising production +301 / -38 and tests +911 / -1; independent `git diff --check` clean.

#### Child-step responsibilities

- **M4.2 — Signal/execution state agreement:** DONE at accepted implementation/validation scope under AD-017.
- **M4.3 — Execution timing and stop/fill validity:** DONE at accepted implementation/validation scope; validates next-open action timing, ordinary and gap stops, single slippage application, event priority, entry-stop validity, no-lookahead marking and end-of-data behavior for Backtest.
- **M4.4 — Account returns and performance metrics:** DONE/CLOSED at accepted implementation/validation scope; preserves instrument-return meaning while deriving account return, drawdown and performance from authoritative portfolio/equity state through a result-aware API.
- **M4.5 — Risk sizing and drawdown validity:** DONE/CLOSED at accepted implementation/validation scope under AD-018; uses current pre-entry equity, transaction-cost-aware cash affordability, sticky period-start-equity entry guards and represented candle-calendar resets.
- **M4.6 — Research manifest and deterministic references:** define hand-calculated reference scenarios, a complete effective run manifest and a versioned successor economic-policy identity without changing AD-015 v1.
- **M4.7 — Backtest validity integration:** validate the complete accepted M4 contract with deterministic reference, boundary, failure, regression and full-suite evidence before milestone closure.

**Dependencies:** M4 builds on M1/M2 authoritative simulated accounting and the completed M3 historical/reproducibility foundation. AD-011 and AD-016 govern its return and economic semantics, and AD-018 owns the accepted M4.5 sizing, affordability and period-loss-guard target. Open or partially resolved deferred items DW-001, DW-002 and DW-009 retain their stated M4 ownership.

**Validation direction:** Use deterministic, hand-calculated scenarios and risk-proportionate success, boundary, failure and regression tests. Compare authoritative executions, cash, positions, equity, trade results, drawdown and versioned research identity. The latest accepted full suite is 443 passed in 9.03s at `57ccfac`; M4.1 remains documentation/design evidence only.

**Non-goals:** WFA validity (M5), live data and paper runtime (M6/M7), authoritative application workflows (M8), V1 release acceptance (M9), real-money execution (V2), exact brokerage/tax fidelity, multi-symbol portfolio semantics and calendar-derived completeness.

M4 is IN_PROGRESS and is not complete. M4.2 through M4.5 are DONE/CLOSED at their accepted scopes; M4.6–M4.7 remain PLANNED and M5 remains RESERVED. The next planned action is a separate M4.6 design/review. M4.6 remains PLANNED and is not automatically implementation-authorized.

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
