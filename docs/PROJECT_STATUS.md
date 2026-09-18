# Kanasu Trading System — Project Status

## Current dashboard

| Field | Current value |
|---|---|
| Project | Kanasu Trading System |
| Migration baseline | 2026-09-13 |
| Branch | `m4-backtest-validity` |
| Documentation governance baseline | `170f618 Restructure Kanasu documentation governance` |
| Implementation verification baseline | `57ccfac Implement M4.5 risk sizing and drawdown validity` |
| Latest reported test baseline | `443 passed in 9.03s at 57ccfac` |
| Current source baseline | `57ccfac` — M4.5 implementation and accepted independent validation |
| Version | V1 — Research and Real-Market-Data Paper Trading |
| Phase | P2 — Trusted Research Engine |
| Milestone | M4 — Backtest Validity |
| Step | M4.5 — Risk sizing and drawdown validity — DONE/CLOSED at accepted implementation/validation scope |
| Lifecycle | M4 IN_PROGRESS; M4.1 through M4.5 DONE at accepted scopes; M4.6–M4.7 PLANNED |
| Next planned review | Separate M4.6 design/review; M4.6 implementation is not automatically authorized |

The independently rerun 443-test full suite passed in 9.03s with exit code 0 at implementation commit `57ccfac`.

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
- M3.8c — Reproducibility identity and research-evidence persistence
- M3.8d — Integration and repeated-run validation
- M3.8 — Historical-path parity and reproducibility
- M3 — Offline / Historical Market-Data Foundation

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

## M3.8c validation evidence

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
- Production defects discovered: none
- Runtime/M3.8d wiring: none

M3.8c implements deterministic type-tagged canonical serialization and versioned, domain-separated SHA-256 fingerprints for canonical datasets, effective Backtest research configuration and stable Backtest results. Dataset identity rejects noncanonical chronology rather than sorting or repairing it. Configuration identity uses effective research values, while stable-result identity covers the current `Trade`, `BarRecord` and equity-curve contract and excludes random `session_id`.

The immutable research-evidence model preserves explicit `ACCEPTED`, `FAILED` and `INCOMPLETE` states. Its dedicated SQLite store remains physically separate from historical candle/coverage storage, rejects duplicate evidence IDs, and supports exact durable reload. Boundary validation requires timezone-aware datetime creation values and ordered list/tuple artifact references of strings; malformed string, bytes, set and mapping inputs are rejected. No production defect was discovered, no AngelOne/network/credentials were required, and no runtime or M3.8d integration was added.

M3.8c does not establish Backtest financial or economic validity. It also does not validate the complete provider-fresh → Backtest → fingerprints → evidence → durable-local repeated-run flow, which remains M3.8d work.

## M3.8d validation evidence

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

Deterministic integration tests validate the complete fresh → historical SQLite persistence → canonical candles → Backtest → dataset/configuration/result fingerprints → separate research-evidence SQLite persistence → durable-local rerun composition. Provider-backed fresh retrieval and durable `LOCAL_ONLY` or warm `LOCAL_FIRST` retrieval produce identical candles, stable trades, `BarRecord` and account/equity state, equity curves, and reproducibility fingerprints. Repeated fresh local-store reads remain identical, while warm covered retrieval does not construct a provider.

Different provenance and session IDs do not change the three reproducibility identities. Accepted evidence reloads exactly from fresh evidence-store instances; duplicate IDs cannot overwrite it; historical and research-evidence SQLite boundaries remain separate; research-relevant configuration changes alter identity; and presentation controls do not. Provider failure creates neither false coverage nor false `ACCEPTED` evidence, while explicit `INCOMPLETE` evidence remains `INCOMPLETE`. Configuration identity used the explicit effective risk value `1.0`, matching current Backtest execution for this validated path. No production correction was required.

M3.8d validates deterministic composition and integration; it does not automatically wire evidence creation into runtime entry points. It does not establish Backtest financial or economic correctness, which remains M4 work.

## M4.2 validation evidence

- Implementation commit: `770d3a5 Implement M4.2 execution feedback contract`
- Focused execution/backtest validation: 26 passed
- Full suite: 323 passed in 6.53s, independently rerun
- Previous accepted full-suite baseline: 309 passed
- Tests added: 14
- Repository line changes: +620 / -13, net +607
- Staged `git diff --check`: passed before commit

M4.2 implements the immutable typed `ExecutionFeedback` contract with accepted/rejected entry, strategy-exit and protective-exit events plus machine-readable rejection reasons. Feedback is emitted after authoritative execution/portfolio outcomes and flows through TradeExecutionEngine → BacktestEngine → StrategyRunner → the optional BaseStrategy hook. Hook failures abort the Backtest, contradictory BUY-while-LONG and SELL-while-FLAT states fail explicitly, and the ordered collection supports multiple events per candle.

`SMACrossOverStrategy` now changes local position belief from execution feedback rather than signal intent. PortfolioManager and execution accounting ownership remain unchanged. PivotBoss and paper-runtime feedback integration remain outside the validated M4.2 scope.

## M4.3 validation evidence

- Design baseline: `d7ee0d937a99e99154b200936560abc67e32704a Baseline M4.3 execution timing design`
- Implementation commit: `bc9409c904ee77db1c3e587931e4ca8209c4d71d Implement M4.3 execution timing validity`
- Focused Codex validation: 41 passed in 1.09s
- Additional Backtest/execution focused validation: 37 passed in 0.19s
- Independent full regression: 334 passed in 7.88s
- Previous accepted full-suite baseline: 323 passed
- Tests added: 11
- Repository line changes: production +338 / -191; tests +415 / -11; total +753 / -202; documentation +0 / -0

M4.3 implements a Backtest-owned immutable pending intent so completed-bar BUY and discretionary SELL decisions execute at the next bar open using snapshotted decision-time stop context. Slippage applies once, an entry stop must remain below the actual fill, and existing-long priority is gap stop → queued SELL → ordinary stop. Gap stops use the candle open; ordinary stops use the stop price; and a next-open entry may produce ordered `ENTRY_ACCEPTED` → `PROTECTIVE_EXIT` feedback when that bar's later low reaches the stop.

Open-time actions precede current-close marking. Final-bar intents remain unfilled, open positions are not automatically liquidated, and surviving positions are marked to the final close. M4.2 contradiction and feedback-handler behavior remain intact. The legacy immediate `on_signal()` path remains available to non-Backtest callers, and PaperRuntime was not migrated. PivotBoss, M4.4+ economics, WFA and later runtime scopes are not part of this validation.

## M4.4 implementation and validation evidence

M4.4 is DONE/CLOSED at its accepted implementation/validation scope. Backtest reporting now uses `PerformanceMetrics.summarize_backtest(result: BacktestResult)`. The existing `PerformanceMetrics.summarize(trades)` remains unchanged as an explicitly legacy trade-only compatibility path for current WFA callers; WFA migration and validity remain M5 work.

The implementation preserves instrument price return, gross monetary trade P&L, net monetary trade P&L and account/equity return as distinct measures. `Trade.pnl_pct` remains instrument fill-to-fill return. For a normal non-empty canonical Backtest, the first `BarRecord.equity` is starting equity under the current M4.3 lifecycle and the last is ending equity. Account P&L, account return and maximum drawdown derive from authoritative equity, so transaction costs and final unrealized marked P&L participate even with zero completed trades. Result-aware programmatic metrics remain unrounded, while Backtest console presentation formats floating-point values to two decimals.

Empty no-bar/no-trade results return the complete zero-valued contract. Trades without equity records, non-finite equity and non-positive starting equity fail explicitly. Negative equity can produce greater than 100% drawdown without clipping. `BacktestResult`, `BarRecord` and `Trade` schemas, `TradeBuilder.pnl_pct` semantics and frozen AD-015 v1 remain unchanged. No M4.5, M4.6 or M5 implementation occurred.

- Design baseline: `259145c0e743156f5b217773fe2b1df34ac93579 Baseline M4.4 account performance design`
- Implementation commit: `7102859ecb80bf932a780825f10634fd36cb0a9d Implement M4.4 account performance metrics`
- Focused validation: 32 M4.4/reporting/WFA-compatibility tests passed; 38 Backtest/execution/portfolio regressions passed; all 8 WFA tests passed; 29 runtime/parity/reproducibility tests passed
- Independent full regression: 364 passed in 6.86s, exit code 0
- Previous accepted full-suite baseline: 334 passed; increase: 30 tests
- Implementation files: production +134 / -3; tests +454 / -0; total +588 / -3
- Independent `git diff --check`: clean

## M4.5 implementation and validation evidence

M4.5 is DONE/CLOSED at its accepted implementation/validation scope under AD-018. Canonical Backtest long entries now size from authoritative current pre-entry `PortfolioManager` equity using actual next-open fill after configured BUY slippage and stop context from the prior completed-bar decision. The same equity owns the max-position cap, while current candle high/low/close cannot influence open-time sizing. Finite/positive validation is explicit, a long stop must remain strictly below actual fill, and invalid long stops produce `INVALID_ENTRY`; non-finite authoritative equity, cash, fill or transaction cost remain invariant failures.

Risk/max-position sizing remains separate from available-cash affordability. Execution selects the largest affordable integer quantity whose actual-fill notional plus enabled entry transaction cost does not exceed authoritative cash. No affordable share produces `INSUFFICIENT_CASH`; accepted entry cost is charged once; rejected attempts preserve authoritative portfolio/trade/cost state and clear execution diagnostics including `last_transaction_cost`; and `PortfolioManager` defensively prevents an accepted long from creating negative cash. `max_position_pct` remains finite and positive without a new 100% configuration cap because cash affordability is the hard unlevered boundary.

Daily and weekly Backtest guards now use sticky period-start authoritative-equity loss rather than period peak-to-current drawdown or accumulated `Trade.pnl` percentages. Realized P&L, unrealized marked P&L and transaction costs participate through equity observed after entry, exit and close marking. Inclusive threshold breach blocks new entries for the remainder of represented candle date or `(ISO year, ISO week)` while exits and protective stops remain allowed and no forced liquidation is introduced. Carried equity from the prior completed/marked bar establishes a new-period baseline before current-period open execution. Non-positive baselines latch without division, non-finite equity fails explicitly and losses greater than 100% are not clipped.

M4.3 execution priority, same-bar post-entry protection and no-lookahead ordering remain intact. Effective Backtest risk now propagates `AppConfig.risk_per_trade_pct` through `RuntimeContext`, `BacktestEngine` and `TradeExecutionEngine`; the compatible context default remains 1%, `BacktestConfig` is unchanged, and frozen AD-015 v1 is unchanged. WFA may inherit corrected shared Backtest mechanics, but WFA-specific configuration, scoring, metrics, stitching, verdicts and economic validity remain M5 work. PaperRuntime/live policy, PivotBoss, multi-symbol redesign, exchange calendars, exact broker/tax fidelity, leverage/margin/shorts/derivatives, forced liquidation, M4.6/M4.7 and API/frontend behavior are outside the closed scope.

- Design baseline: `78e4493430dab2a9389bfda4e41b1149ef038f7f Baseline M4.5 risk sizing design`
- Implementation commit: `57ccface0f086dd12e38fca9cfed3b5aa92fbe9c Implement M4.5 risk sizing and drawdown validity`
- Focused M4.5/regression validation: 193 passed in 3.01s
- Independent full regression: 443 passed in 9.03s, exit code 0
- Previous accepted full-suite baseline: 364 passed; increase: 79 tests
- Implementation files: production +301 / -38; tests +911 / -1; total +1212 / -39
- Independent `git diff --check`: clean

## Current work

M3.1 through M3.8 remain complete at their accepted scopes, and M3 — Offline / Historical Market-Data Foundation remains DONE. The latest accepted implementation evidence is `57ccfac Implement M4.5 risk sizing and drawdown validity` with an independently passing 443-test full suite.

The M4 design audit used source baseline `6a0ab9a`. It confirmed that M4 owns the remaining Backtest validity contracts: completed-bar decisions and next-bar execution, protective-stop and gap behavior, deterministic event priority, strategy/execution state agreement, account-based returns and drawdown, current-equity risk sizing and affordability, simplified brokerage application, end-of-data handling, and versioned economic-policy research identity.

M4 — Backtest Validity remains IN_PROGRESS. M4.2 through M4.5 are implemented and validated at their accepted scopes. Its permanent child steps are:

- M4.1 — Backtest economic contract — DONE at accepted design-contract scope
- M4.2 — Signal/execution state agreement — DONE at accepted implementation/validation scope
- M4.3 — Execution timing and stop/fill validity — DONE at accepted implementation/validation scope
- M4.4 — Account returns and performance metrics — DONE/CLOSED at accepted implementation/validation scope
- M4.5 — Risk sizing and drawdown validity — DONE/CLOSED at accepted implementation/validation scope
- M4.6 — Research manifest and deterministic references — PLANNED
- M4.7 — Backtest validity integration — PLANNED

M4.1 records target behavior only; it adds no implementation or validation evidence. M4.2 is implemented and validated for the Backtest/`SMACrossOverStrategy` scope under AD-017. PivotBoss and paper-runtime integration remain outside that claim.

M4.3 now implements and validates completed-bar decisions, one pending intent, next-open BUY/SELL execution, decision-time stop context, gap-stop/queued-SELL/ordinary-stop priority, exact single slippage, same-bar post-entry protection, execution-before-close-mark ordering, and end-of-data handling for Backtest.

M4.4 now implements and validates result-aware authoritative Backtest metrics, equity-derived account return and maximum drawdown, explicit completed-trade monetary and instrument-return statistics, zero-trade/open-position behavior, failure boundaries and full-precision programmatic results while preserving the legacy WFA compatibility path.

M4.5 now implements and validates AD-018 current-equity sizing, transaction-cost-aware affordability, period-start-equity guards, calendar-period transitions, mutation-free rejection behavior and effective Backtest risk propagation at the accepted Backtest scope. The next planned action is a separate M4.6 design/review. M4.6 remains PLANNED and is not automatically implementation-authorized. Existing open and deferred concerns remain governed by the deferred-work ledger.

## Important V1 blockers

- backtest financial and economic validity;
- WFA termination, configuration propagation, and account-metric validity;
- real-market-data ingestion for paper trading;
- an operational paper-session lifecycle;
- API/frontend integration with actual runtime and research results; and
- completion of all V1 validation and release gates.

Technical findings that are deliberately unresolved are recorded in [Deferred Work](roadmap/DEFERRED_WORK.md). The ordered delivery plan is in the [Roadmap](roadmap/ROADMAP.md).

## Release boundary

V1 does not place real-money broker orders. Live execution is deferred to V2 and requires additional execution, reconciliation, recovery, operational-safety, and external acceptance evidence.
