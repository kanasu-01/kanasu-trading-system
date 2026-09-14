# Kanasu Trading System — Project Status

## Current dashboard

| Field | Current value |
|---|---|
| Project | Kanasu Trading System |
| Migration baseline | 2026-09-13 |
| Branch | `m3-offline-foundation-data` |
| Documentation governance baseline | `170f618 Restructure Kanasu documentation governance` |
| Implementation verification baseline | `388b5393 Validate M3.8b backtest result parity` |
| Latest reported test baseline | `248 passed at 388b5393` |
| Version | V1 — Research and Real-Market-Data Paper Trading |
| Phase | P1 — Trusted Historical Data Foundation |
| Milestone | M3 — Offline / Historical Market-Data Foundation |
| Step | M3.8 — Historical-path parity and reproducibility |
| Lifecycle | IN_PROGRESS |
| Next implementation candidate | M3.8c — Reproducibility identity and research-evidence persistence; implementation requires separate explicit authorization |

The 248-test full suite was rerun at implementation and validation commit `388b5393` and passed.

## Completed foundation

- M0 — Repository / foundation hygiene
- M1 — Authoritative simulated portfolio accounting
- M2 and M2.1–M2.4 — Execution economics/accounting correctness
- M3.1 — Candle finite-value validation
- M3.2 — Canonical CSV candle loader
- M3.3a — Dataset identity propagation
- M3.3b — Dataset timezone identity as metadata
- M3.4 — Candle sequence integrity
- M3.5 — Safe historical chunk composition
- M3.6a — SQLite candle persistence
- M3.6b — Coverage and missing-range planning
- M3.6c — Local-first historical retrieval service
- M3.6d — Integration and failure validation
- M3.6 — Local historical persistence and retrieval
- M3.7a — Historical source policy contract
- M3.7b — Broker historical provider adapter
- M3.7c — Backtest/WFA runtime wiring and lazy provider construction
- M3.7d — Source-policy integration and failure validation
- M3.7 — Historical source policy/runtime wiring
- M3.8a — Historical input parity
- M3.8b — Backtest result parity

Completion here refers to the accepted scope of each historical task. It does not imply that every component is integrated into a V1 workflow or release-ready.

## M3.6b validation evidence

- Focused historical coverage tests: 25 passed
- All market-data tests: 51 passed
- Full suite: 111 passed
- `git diff --check`: passed
- Implementation commit: `1e8065a Add historical coverage planner`

## M3.6c validation evidence

- Focused M3.6c/store tests: 57 passed
- All market-data tests: 99 passed
- Full suite before commit: 159 passed
- Full suite after commit `1c4a877`: 159 passed
- `git diff --check`: passed
- Implementation commit: `1c4a877 Add local-first historical retrieval`

The accepted M3.6c contract keeps persistent retrieval coverage separate from stored candles. Fully covered requests avoid provider calls, and uncovered requests fetch only missing retrieval ranges. Confirmed-empty coverage is valid evidence; partial results persist only explicit coverage; and provider failures or results without coverage evidence create no false claim. Accepted candles and coverage are persisted transactionally.

Service requests and coverage use half-open `[start, end)` intervals while SQLite candle reads remain inclusive. A `DatasetContext` cannot mix naive and aware persisted timestamps, but different aware offsets remain supported through Python datetime semantics. Equivalent aware timestamps for the same instant are one candle identity, with the first stored representation retained. No timezone normalization was introduced.

## M3.6d validation evidence

- Focused M3.6d integration suite: 11 passed
- M3.6 coverage/store/retrieval/integration neighborhood: 93 passed
- All market-data tests: 110 passed
- Full suite: 170 passed
- Post-commit full suite: 170 passed
- `git diff --check`: passed
- Validation commit: `dc5bda3 Add M3.6d integration validation`
- Production code changes: none

The integration evidence proves that complex cold retrieval becomes durable warm retrieval and that fully covered durable state avoids provider calls. Earlier accepted gaps survive a later provider failure, rollback is scoped to the failing provider result, and partial retrieval resumes only the actual remaining gaps. Raw overlapping or touching coverage is reconciled by the planner. Incompatible persisted/request awareness fails before provider access, while legacy same-instant cross-offset duplicate rows are rejected rather than repaired. Half-open service boundaries remain correct after durable reload, confirmed-empty coverage remains durable evidence, and `DatasetContext` isolation holds across complete retrieval lifecycles.

M3.6d required no production correction. The existing M3.6c implementation satisfied all new integration cases.

## M3.7a validation evidence

- Implementation commit: `073f3e9 Add historical source policy contract`
- Focused M3.7a: 16 passed
- M3.6 + M3.7a neighborhood: 109 passed
- All market-data: 126 passed
- Full suite: 186 passed
- `git diff --check`: passed

M3.7a establishes explicit `LOCAL_ONLY`, `LOCAL_FIRST` and `PROVIDER_BACKED` policies. `LOCAL_ONLY` never invokes a provider. Warm `LOCAL_FIRST` also avoids provider construction, while missing coverage lazily creates one provider and reuses it across every missing gap. `PROVIDER_BACKED` always accesses the provider for the complete request, and completion depends only on that call's explicit coverage; old local coverage cannot mask partial provider evidence. Confirmed-empty provider evidence is valid.

Provider-backed persistence remains non-destructive, and no refresh or replacement policy was introduced. `RuntimeMode` remains independent. M3.7a added no broker, AngelOne, HistoricalFeed, main, backtest or WFA wiring, and introduced no timestamp normalization or expected-bar, calendar or session inference.

## M3.7b validation evidence

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

`HistoricalFeedProvider` implements the accepted `HistoricalProvider` shape by composing `HistoricalFeed`; it does not duplicate broker chunking. HistoricalFeed remains authoritative for broker limits, chunk traversal, overlap handling, duplicate and conflict detection, chronology, and stream-awareness validation. A successfully completed retrieval returns explicit `coverage=(request,)` based on operation completion rather than candle count or spacing, so sparse and confirmed-empty results remain valid evidence.

The adapter includes a candle at `request.start`, excludes an exact `request.end` candle under half-open `[start, end)` semantics, and rejects other out-of-range candles rather than clipping them. Failed streams return no result or manufactured coverage, including failures after earlier chunks emitted candles. Request/candle naive-aware incompatibility fails explicitly, with no timestamp normalization or conversion.

AngelOne now returns `[]` for a valid `data=[]` response. Malformed responses remain errors, and non-empty timestamp/OHLCV parsing remains unchanged. BaseBroker, HistoricalFeed, HistoricalSource, AppConfig, main, backtest and WFA runtime were unchanged. No expected-bar, session, calendar or gap-inference logic was added.

## M3.7c validation evidence

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
- Interpreter: `.\.venv\Scripts\python.exe` using Python 3.11.9

Backtest and WFA now obtain canonical historical candles through `HistoricalSource`. They no longer depend directly on BaseBroker or HistoricalFeed and contain no source-policy branching. Source composition creates the local SQLite capability immediately, including the database parent directory when needed, but it does not load AngelOne credentials, construct AngelOneBroker or log in. Only the lazy provider closure calls `create_angelone_broker(paper_mode=True, enable_historical_api=True)`, constructs HistoricalFeed with the configured request delay, and wraps it in HistoricalFeedProvider.

At the M3.7c scope, complete `LOCAL_ONLY` and warm `LOCAL_FIRST` retrieval require no external construction. Missing `LOCAL_FIRST` coverage invokes the provider only after local coverage is examined, and `PROVIDER_BACKED` invokes the provider despite complete local coverage. `HistoricalSource` remains the sole policy owner.

`AppConfig` now owns `historical_source_policy`, `historical_database_path` and `historical_request_delay_sec`, with defaults `HistoricalSourcePolicy.LOCAL_FIRST`, `data/historical.sqlite3` and `0.5`. `load_app_config()` supports `HISTORICAL_SOURCE_POLICY`, `HISTORICAL_DATABASE_PATH` and `HISTORICAL_REQUEST_DELAY_SEC`. Main no longer constructs or authenticates AngelOne before runtime selection; it composes HistoricalSource only for BACKTEST and WALK_FORWARD. M3.7c added no historical-source composition to PAPER or LIVE.

The default AngelOne-oriented BacktestConfig uses explicit Asia/Kolkata-aware request boundaries. This is explicit configuration rather than runtime localization: DatasetContext timezone remains metadata, timestamp values pass through unchanged, and awareness incompatibility remains an explicit failure. M3.7c did not change HistoricalSource, HistoricalFeedProvider, HistoricalFeed, BaseBroker, AngelOne historical parsing, historical retrieval validation or SQLite coverage semantics. The broker factory remains source-policy unaware and eager only when called.

## M3.7d validation evidence

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

M3.7d validated the actual Backtest and WFA source-composition paths across fully offline `LOCAL_ONLY`, warm `LOCAL_FIRST`, missing-range durable reuse, mandatory `PROVIDER_BACKED` access, credential/construction/login and retrieval failures, confirmed-empty evidence, timestamp-awareness incompatibility, and common source-policy semantics. External failures create no false retrieval coverage, accepted earlier results remain durable, and errors and captured logs do not expose the exercised secret value. The existing production implementation satisfied the accepted integration matrix without correction.

## M3.8a validation evidence

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

M3.8a proves that equivalent provider-fresh historical data persists through SQLite and reproduces identical canonical candles from fresh local-store instances through both `LOCAL_ONLY` and warm `LOCAL_FIRST`. Candle count, chronology, timestamp representation and OHLCV values remain equal; half-open `[start, end)` boundaries include the request start and exclude the exact request end; confirmed-empty evidence remains durable without warm provider construction; and `DatasetContext` isolation holds. The deterministic validation uses no AngelOne, network or credentials and required no production correction.

M3.8a completion does not validate M3.8b Backtest-result parity, M3.8c fingerprint/evidence persistence or M3.8d full integration.

## M3.8b validation evidence

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

M3.8b proves that equivalent accepted historical data, identical deterministic strategy behavior, identical research-relevant Backtest configuration and identical execution configuration produce exactly equal stable Backtest results through provider-fresh and durable-local paths. The validated paths are provider-backed fresh to `LOCAL_ONLY`, provider-backed fresh to warm `LOCAL_FIRST`, and cold `LOCAL_FIRST` to warm `LOCAL_FIRST`.

Stable parity covers complete `Trade` records, `BarRecord` sequences, strategy/execution events, execution prices and quantities, cash, equity, position size, drawdown and the canonical equity curve. Random `session_id` values deliberately differ and are excluded from stable research-result parity. No production correction was required.

M3.8b does not validate Backtest economic correctness; timing, fill or stop correctness; fingerprinting or canonical serialization; research-evidence persistence; WFA validity; or full M3.8 integration.

## Current work

M3.7a through M3.7d are complete at their accepted scopes. M3.7 — Historical Source Policy / Runtime Wiring is DONE.

DW-011 is resolved by the accepted M3.7d evidence. M3.8 — Historical-path parity and reproducibility is IN_PROGRESS. Its permanent child steps are:

- M3.8a — Historical input parity — DONE
- M3.8b — Backtest result parity — DONE
- M3.8c — Reproducibility identity and research-evidence persistence — BASELINED / NOT AUTHORIZED
- M3.8d — Integration and repeated-run validation — BASELINED

M3.8 will prove that equivalent accepted historical data and research-relevant configuration produce equivalent canonical input and stable Backtest output through provider-fresh and warm local-store paths. It will also establish deterministic dataset, configuration and result fingerprints plus a separate research-evidence persistence boundary. Provider-fresh and missing-range retrieval already persist accepted data before reloading canonical candles from SQLite, while `LOCAL_ONLY` and warm `LOCAL_FIRST` read from that same store; M3.8 validates that these paths converge without redesigning them unless focused RED evidence proves a defect.

M3.8a and M3.8b are complete at their accepted scopes. M3.8c is the next implementation candidate but remains NOT AUTHORIZED; coding requires separate explicit authorization. M3.8d remains baselined and unimplemented.

## Important V1 blockers

- historical-path parity and reproducibility;
- backtest validity and reproducible research records;
- WFA termination, configuration propagation, and account-metric validity;
- real-market-data ingestion for paper trading;
- an operational paper-session lifecycle;
- API/frontend integration with actual runtime and research results; and
- completion of all V1 validation and release gates.

Technical findings that are deliberately unresolved are recorded in [Deferred Work](roadmap/DEFERRED_WORK.md). The ordered delivery plan is in the [Roadmap](roadmap/ROADMAP.md).

## Release boundary

V1 does not place real-money broker orders. Live execution is deferred to V2 and requires additional execution, reconciliation, recovery, operational-safety, and external acceptance evidence.
