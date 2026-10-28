# Kanasu Trading System — Project Status

## Current dashboard

| Field | Current value |
|---|---|
| Project | Kanasu Trading System |
| Migration baseline | 2026-09-13 |
| Branch | `m9-v1-research-platform` |
| Documentation governance baseline | `2a305a5 Optimize agent context loading` |
| M8 starting baseline | `390c7cc` — `Close M7 documentation and advance roadmap` |
| M8 design baseline | `f86a6dd` — `Baseline M8 research and paper application design` |
| M8.5 closure parent baseline | `83ae719` - `Harden AngelOne login retry configuration` |
| Latest M9.4 corrective validation | Consolidated correction ACCEPTED_CLOSED at `87d740d9d5558821088d8095fd4cf59dcb81bee6` after actual published-state Review 2 PASS and Human Approval 3. Attributable validation: 66 focused, 273 affected-module, 609 M9.4 and 1,750 full Python tests; separate independent execution passed 1,750 tests plus 32 adversarial checks. Actual final CI run [40703344719](https://github.com/kanasu-01/kanasu-trading-system/actions/runs/40703344719) passed. See [closure governance checkpoint](#m94q-closure-governance-publication-checkpoint--2026-10-28). |
| Latest M8.5 frontend validation | `17 passed`; production build passed; lint passed |
| Latest M8.5 closure checks | placeholder/drift search found none; responsive desktop/mobile browser smoke passed; `git diff --check` passed |
| Version | V1 — Research and Real-Market-Data Paper Trading |
| Phase | P5 — V1 Research Platform Completion |
| Milestone | M9 — V1 research platform completion |
| Step | Four-defect stabilization is ACCEPTED_CLOSED. Complete the bounded prospective milestone-closure governance publication, actual-state Review 2 and explicit final milestone acceptance. Exact section 7.1 wording has Human Approval 1 and formal governance Review 1 PASS. R004 remains ACCEPTED_CLOSED. |
| Lifecycle | M0–M8 complete; M9.2/M9.3 closed; M9.4q remains OPEN/BLOCKED at this governance publication checkpoint. The accepted correction is not reopened. Section 7.1 requires exact approved publication/read-back, actual-state Review 2 and explicit milestone Human Approval 3 before DONE. Historical integration/protected-operation approvals and original audit-report F06 remain NOT_VERIFIED; the historical 90-control selector remains unidentified. M9.5 admission and implementation remain BLOCKED. |
| Gate to M9.5 | Requires independent technical and documentation acceptance of the exact final published HEAD and the required attributable human acceptance/authority records. Reported M9.5 Draft v0.3 design-review PASS WITH NONBLOCKING OBSERVATIONS does not grant admission or implementation authority. |

M9 expands the previously reserved release-only scope into completion of the V1 research product. M9.1 is documentation/design only: it defines the persistent research workflow, research identities and state axes, universe semantics, qualification authority, Candidate/PaperCampaign lineage, and behavioral-specification governance. It does not modify Backtest economics, WFA mathematics, Paper causality, historical-source semantics or the real-money boundary.

M9.2 is DONE/CLOSED at its accepted implementation and validation scope. It implements the durable research catalog, immutable content-addressed Backtest artifacts, deterministic `ExperimentSpec` identity, distinct `RunAttempt` identity, automatic reproducibility evidence and restart-safe execution lineage while preserving the accepted M3/M4 fingerprint, manifest, ResearchEvidence and financial-result contracts.

M9.2 began from the clean 111-focused / 792-full-test baseline. The accepted implementation chain is `07f4be1` M9.2a, `24cdf67` M9.2b, `ba2129f` M9.2c, `d21c204` M9.2d, `0f4cc98` M9.2e and `4b44050` M9.2f after design baseline `4eb28d8`. Final committed-head closure validation at `4b44050` passed 198 focused research/API tests and 897 complete Python tests with `git diff --check` clean.
M9.3 is DONE/CLOSED at its accepted instrument, universe and dataset-truthfulness scope. M9.3a established canonical instrument/provider-binding contracts (`5543b30`); M9.3b immutable/effective-dated universe snapshots (`61ec27c`); M9.3c successor dataset identity/provenance (`1505141`); M9.3d AngelOne binding/wall-time behavior (`27baa26`); and M9.3e completed acquisition-stream persistence, binding-aware historical retrieval, durable DatasetReference evidence and an explicit opt-in Backtest application path through published head `8d70d1e`. The legacy/default Backtest path remains unchanged because Kanasu does not manufacture canonical instrument or effective-dated provider truth from the temporary RELIANCE token map. M9.3f closes validation, behavioral traceability and authoritative-document synchronization. The complete Python regression is 1078 passing tests and `git diff --check` is clean. DW-019 remains resolved at its bounded M9.3d adapter scope.
Historical M9.4 publication and correction sequence follows; its intermediate
publication and gate statements are not the current dashboard.

M9.4 was historically published DONE/CLOSED against accepted design baseline `9b7ab42`, with M9.4f at `b93ae6a`. M9.4g corrected the first independent-audit findings and was historically re-closed at `68df76b`. M9.4h then corrected residual N01-N07 findings and was published through h4 at `306c156a5b58edb8a4dd6331409d473bc08af98b`. The independent re-review of that exact head returned `M95_GATE=BLOCKED` with H01-H05. M9.4i addresses H01 canonical executable procedure authority, H02 supported exact-reuse artifact authority, H03 fail-closed authoritative filesystem failures, H04 complete-population proof authority, and H05 validation-evidence precision. The corrective candidate is published at `eab3c742ca5fbe0d7e058bb4cc8db758803848ab` and post-push verification confirmed local and remote HEAD equality plus the exact 17-file committed manifest. Validation evidence is 153 H01-H04 focused tests, 245 repository-wide `test_m94*.py` tests, 251 semantic `-k m94` tests with 1098 deselected, 1349 complete Python tests, and clean `git diff --check`. This publication is not proof that the independent re-review passed. M9.5 remains blocked until the independent review of `eab3c742ca5fbe0d7e058bb4cc8db758803848ab` returns `M95_GATE=PASS`. A subsequent independent post-publication audit identified R01-R06. M9.4j preserves the accepted M9.4 architecture while correcting complete frozen Backtest financial configuration identity; strict separation between standalone M9.2 RunAttempt lifecycle authority and ResearchJob-owned attempt authority; canonical Backtest-result validation before exact reuse; rejection of obviously impossible finite result states; one-transaction Trial-detail lineage snapshots; and current-state documentation drift. M9.4j is published and post-push verified at `7f123daa135be4009294f5197676dc5153261255`. The subsequent independent audit returned `M95_GATE=BLOCKED`: F01 found that an empty or incomplete registered data-treatment mapping could bypass explicit price-adjustment authority; F02 found that canonical Backtest-result validation still admitted several impossible long-only states; and F03 identified current-state documentation drift. M9.4k preserves the accepted architecture while requiring explicit `raw` / `adjusted` / `unknown` price-adjustment registration, failing incomplete historical plans closed, strengthening only direct long-only canonical-result invariants, adding real registration/execution and canonical reuse/aggregation counterexample tests, correcting stale historical test fixtures, and synchronizing current-state documentation. M9.4k was subsequently separately reviewed, staged, committed and pushed at `9ac407fd4910edf9392445a6fa0539ba90fa97c5`, with local/remote post-push equality verified. The fresh independent audit of that exact published head returned `M95_GATE=BLOCKED`: F05 found that public raw registered fresh-execution persistence phases could bypass frozen StudyRevision semantics; F04 found remaining impossible canonical-result states; F06 found inconsistent restart-recovery chronology when RunAttempt creation post-dated the supplied recovery clock; and F03 found current-state documentation drift. M9.4l preserves the accepted architecture by keeping raw registered fresh-execution persistence phases internal behind the validated claimed-job authority, requiring nonnegative transaction cost, a `[-1, 0]` stored drawdown bound when equity is nonnegative, complete execution event/price/quantity tuples, and one coherent restart-recovery terminal timestamp. M9.4l was published/post-push verified at `d26d3d62b6e7cced738bdbf260269497e0e70d5d`. Its local validation included 176 focused tests, 207 research-only M9.4 tests across 13 modules and 1383 complete Python tests. The independent reviewer subsequently discovered 273 repository-wide M9.4 tests across 21 modules and independently ran all 1383 Python tests. The audit returned `M95_GATE=BLOCKED` with A01, A02, A03 and F03. Publication and passing tests did not establish independent acceptance. At the 2026-10-11 pre-publication validation checkpoint, M9.4m was a local, unstaged and unpublished corrective candidate. This is a historical checkpoint statement, not an assertion about its eventual publication state. A01 adds direct canonical financial consistency checks for net/gross/cost and single-symbol close-marked equity. A02 includes durable cancellation-request time in the shared restart-recovery terminal timestamp. A03 separates public standalone prepared execution from internal supplied-RunAttempt execution and rejects stale attempts before computation; a concurrent claimed-job test verifies one physical execution through that supported entry path. Existing M4 Backtest economics, M5 WFA, M6/M7 Paper causality, M8 application authority, M9.3 data truth and the no-live-order boundary are retained.

The V1 research target remains single-user NSE cash-equity research with long-only, unlevered simulated execution. The supported V1 execution timeframes remain 5m and 15m. Universe research means independent per-instrument simulated accounts plus research aggregation; it does not establish shared-capital multi-symbol portfolio economics.

M8.1-M8.4 implementation is committed through `3694a2e07cd43289b68cd8bb04755d2c508ff67a`. M8.5 closure validation ran on parent baseline `83ae719f15ba0d5f681b35b955dbf46cad6b8ce9`. The closure candidate adds integration tests, synchronized closure documentation and a bounded responsive-shell correction; it does not change Backtest/Paper trading authority, broker/runtime semantics or the real-money boundary.
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
- M4 — Backtest Validity
- M5 — Walk-Forward Analysis Validity
- M6 — Live Market-Data Foundation
- M7 — Paper-Session Integration through M7.9

Completion here refers to each milestone's accepted scope. M8 application integration is also DONE/CLOSED at its accepted scope. M9 now owns the additional research-product workflow, evidence governance, persistent application research lifecycle and final V1 research-ready acceptance defined by the M9 design.

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

Complete one bounded governance/documentation publication for the human-approved prospective M9.4q completion basis in [Governance section 7.1](governance/GOVERNANCE.md#71-m94q-bounded-prospective-completion). Formal independent governance Review 1 PASS is preserved in the [approved comparison and review record](governance/reviews/M94Q_SECTION7_1_REVIEW_RECORD.md). That review found no Global SOP amendment or new technical audit necessary for this exact prospective basis. Its scope is current-state milestone acceptance with unresolved historical provenance preserved, not retrospective process-compliance approval.

The consolidated four-defect correction at `87d740d9d5558821088d8095fd4cf59dcb81bee6` is ACCEPTED_CLOSED after final technical/documentation Review 2 PASS and owner Human Approval 3. Preserve R004, unchanged RO-01 V002 and all accepted M4–M9.4 contracts. Section 7.1 only becomes governing after exact approved publication and successful read-back; the governance actual-state Review 2 and explicit Human Approval 3 for milestone closure remain distinct completion gates. No draft approval, local file or technical PASS supplies publication authority, closes M9.4q or admits M9.5.

## Historical work records

> Historical record scope: M9.4q review and checkpoint records below describe
> their recorded candidates, including then-current publication claims, test
> counts and reported authorizations. They are not current branch-state or
> original human-approval evidence. Current status is owned by
> [Project Status](#current-dashboard). Accepted technical contracts remain in force;
> the IND-01 correction supersedes earlier plan-first resolver wording.

M9.4q second corrective checkpoint (2026-10-14): the first M9.4q candidate corrected M94-AUD-01 by enforcing whole-share bar-record `position_size` and reconciled most M94-AUD-02 documentation. A fresh independent candidate audit then returned `M94Q_AUDIT_GATE=BLOCKED`. M94Q-AUD-01 found that hash-valid canonical results could still contain negative authoritative cash with positive whole-share holdings and pass decoding, exact reuse and Study aggregation, despite AD-018's unlevered available-cash affordability contract. M94Q-AUD-02 found the AD-025 current status stale. M94Q-AUD-03 found the required M9.4q categorical behavior-impact declaration missing. M94Q-AUD-04 found review-bundle patch/exclusion reproducibility defects; that bundle issue did not invalidate the repository-backed audit but must be repaired before the next handoff. The current committed branch HEAD remains `0f679f9c24352dea46cff965f49eb4a53f5e9eed`; the second M9.4q correction is local, unstaged and unpublished. The shared canonical Backtest-result validator now rejects `cash < 0` without normalization or tolerance, preserves exactly zero cash for fully funded whole-share holdings, and retains the whole-share `position_size` correction. Regression evidence covers real M4 canonical boundaries, direct and stable-decoder validation, hash-valid persisted exact-reuse rejection without a fabricated RunAttempt, subsequent fresh execution, and both EXECUTED and REUSED Study aggregation. Current second-correction validation passes 30 focused `m94q_` tests, 129 complete tests across the three touched modules, 333 exact repository-wide M9.4 tests across the established 21 modules, and 1457 complete Python tests; `git diff --check` is clean. The earlier 328/1451 counts remain historical evidence for the first M9.4q candidate, not current closure proof. M9.5 Gate A design remains accepted/frozen, but substantive M9.5 implementation remains blocked until the locally validated corrected candidate is separately independently reviewed, is published only through the protected Git approval gates, and the exact published HEAD receives the required independent PASS.

M9.4q revised unpublished candidate validation checkpoint (2026-10-15; `KANASU_900150`): The bounded correction addresses M94Q-NEW-01 (trade timestamps outside authoritative bar history), M94Q-NEW-02 (oversized canonical integers raising uncontrolled `OverflowError`), and M94Q-NEW-03 (contradictory current validation evidence). `KANASU_900147` established five permanent RED regression cases. After the production correction, `KANASU_900148` passed those five cases, five reviewer-authored adversarial cases, and 35 focused `m94q_` cases. `KANASU_900150` subsequently passed 134 touched-module tests, 338 M9.4 tests across 21 modules, and 1,462 full Python tests, without failures, errors or skips. The saved validation summary has SHA-256 `6c5fd30e8384993ba81960f6c9b36d6431e403f30411ae62c7cfa4ba7426a04c`. These are local validation results, not independent acceptance. The latest independent pre-publication verdict remains `M94Q_AUDIT_GATE=BLOCKED` for the earlier candidate; the revised candidate still requires a fresh independent PASS. It remains unstaged and unpublished, and substantive M9.5 implementation remains blocked. Protected stage, commit and push operations require separate human approval.

As of the 2026-10-11 local M9.4n corrective checkpoint, published M9.4m commit `6e248a2749f162738e75258d8cd972a8e037c6b4` has independent `M95_GATE=BLOCKED` findings B01 MEDIUM and F03 LOW. The B01 shared canonical closed-LONG-trade consistency checks and persisted artifact/decoder regressions passed 70 focused tests. The stale design introduction is corrected in this local candidate. Full regression passed 1403 Python tests and 287 repository-wide M9.4 tests across 21 modules. Separately approved staging, commit, push, and independent review of the exact published corrective HEAD remain required. M9.5 remains blocked.

M9.4l was published/post-push verified at `d26d3d62b6e7cced738bdbf260269497e0e70d5d`. Its local validation included 176 focused tests, 207 research-only M9.4 tests across 13 modules and 1383 complete Python tests. The independent reviewer subsequently discovered 273 repository-wide M9.4 tests across 21 modules and independently ran all 1383 Python tests. The audit returned `M95_GATE=BLOCKED` with A01, A02, A03 and F03. Publication and passing tests did not establish independent acceptance. At the 2026-10-11 pre-publication validation checkpoint, M9.4m was a local, unstaged and unpublished corrective candidate. This is a historical checkpoint statement, not an assertion about its eventual publication state. A01 adds direct canonical financial consistency checks for net/gross/cost and single-symbol close-marked equity. A02 includes durable cancellation-request time in the shared restart-recovery terminal timestamp. A03 separates public standalone prepared execution from internal supplied-RunAttempt execution and rejects stale attempts before computation; a concurrent claimed-job test verifies one physical execution through that supported entry path. Existing M4 Backtest economics, M5 WFA, M6/M7 Paper causality, M8 application authority, M9.3 data truth and the no-live-order boundary are retained. Local M9.4m validation passed 1394 complete Python tests and 280 repository-wide M9.4 tests across 21 modules; `git diff --check` passed. At the 2026-10-11 pre-publication checkpoint, `M95_GATE=BLOCKED`. The required release sequence is final review, separately approved stage, commit and push, verification of the exact published HEAD, and a fresh independent post-publication M9.4 audit. Only an explicit `M95_GATE=PASS` for the audited published HEAD authorizes fresh M9.5 design; it does not authorize M9.5 implementation.

M8.5 closed application integration validation on parent baseline `83ae719 Harden AngelOne login retry configuration` while preserving the accepted M8.1-M8.4 application architecture.

The accepted M8 implementation chain is:

- design baseline `f86a6dd` — research and paper application design;
- M8.1 `a31ad067` — application contracts and composition;
- M8.2 `9ec54f1` — authoritative Backtest API;
- M8.3 `e57e085` — authoritative Paper control plane; and
- M8.4 `3694a2e` — authoritative frontend workflows.

The Backtest application now executes the real historical-source → validated strategy → `BacktestEngine` path, exposes the actual `BacktestResult.session_id`, uses result-aware account/trade metrics and projects authoritative equity/trade results.

The Paper application now owns one process-local authoritative M7 runtime handle, exposes `PaperTradingSession.snapshot()` state, controls the real runtime stop path, waits for worker termination and retains terminal `STOPPED` or `FAILED` state.

The frontend consumes these authoritative Backtest and Paper contracts through environment/same-origin API configuration. It does not independently reconstruct portfolio, P&L, drawdown or lifecycle authority.

M8.5 validation is green. API/application validation passes 58 tests; the complete Python regression passes 792 tests. Frontend validation passes 17 tests across five files, production build and lint pass, the placeholder/drift search finds no matches and `git diff --check` passes. M8.5c applies only a bounded responsive application-shell correction and truthful Portfolio coming-soon wording. Desktop and Tailscale-connected mobile browser smoke passed for the Home, Backtest and Paper UI; live Paper start was intentionally not exercised during browser smoke.

M8.5 implementation and validation evidence is complete at the accepted application scope. Normal repository review, staging, commit and publication gates remain procedural controls and do not expand the validated scope.

M8 preserves the validated M4/M5/M7 execution and accounting semantics. Real-money execution, multi-symbol portfolio semantics, PivotBoss validation, process-restart recovery, unrelated legacy replay/export repair and broad broker-authentication redesign remain outside M8.

DW-013 is resolved at the implemented M8 application scope. DW-015 remains open for broker-session/authentication lifecycle hardening. DW-016 records the separately deferred AngelOne negative-volume historical-data anomaly; no fix is included in M8.
## Important V1 blockers

- disposition remaining V1 operational-hardening boundaries, including DW-015 broker-session/authentication lifecycle and unsupported process-restart recovery;
- preserve the explicit deferral of DW-016 unless separately authorized; and
- complete M9 end-to-end V1 acceptance and release validation.

Technical findings outside the active implementation scope are recorded in [Deferred Work](roadmap/DEFERRED_WORK.md). The delivery plan is in the [Roadmap](roadmap/ROADMAP.md).
## Release boundary
V1 does not place real-money broker orders. Live execution is deferred to V2 and requires additional execution, reconciliation, recovery, operational-safety, and external acceptance evidence.

## Superseded M9.4q dashboard snapshot - 2026-10-14

Historical dashboard narrative retained from the previous checkpoint. Its validation counts and candidate state are superseded by the following 2026-10-15 local checkpoint.

M9.4q second corrective checkpoint (2026-10-14): the first M9.4q candidate corrected M94-AUD-01 by enforcing whole-share bar-record `position_size` and reconciled most M94-AUD-02 documentation. A fresh independent candidate audit then returned `M94Q_AUDIT_GATE=BLOCKED`. M94Q-AUD-01 found that hash-valid canonical results could still contain negative authoritative cash with positive whole-share holdings and pass decoding, exact reuse and Study aggregation, despite AD-018's unlevered available-cash affordability contract. M94Q-AUD-02 found the AD-025 current status stale. M94Q-AUD-03 found the required M9.4q categorical behavior-impact declaration missing. M94Q-AUD-04 found review-bundle patch/exclusion reproducibility defects; that bundle issue did not invalidate the repository-backed audit but must be repaired before the next handoff. The current committed branch HEAD remains `0f679f9c24352dea46cff965f49eb4a53f5e9eed`; the second M9.4q correction is local, unstaged and unpublished. The shared canonical Backtest-result validator now rejects `cash < 0` without normalization or tolerance, preserves exactly zero cash for fully funded whole-share holdings, and retains the whole-share `position_size` correction. Regression evidence covers real M4 canonical boundaries, direct and stable-decoder validation, hash-valid persisted exact-reuse rejection without a fabricated RunAttempt, subsequent fresh execution, and both EXECUTED and REUSED Study aggregation. Current second-correction validation passes 30 focused `m94q_` tests, 129 complete tests across the three touched modules, 333 exact repository-wide M9.4 tests across the established 21 modules, and 1457 complete Python tests; `git diff --check` is clean. The earlier 328/1451 counts remain historical evidence for the first M9.4q candidate, not current closure proof. M9.5 Gate A design remains accepted/frozen, but substantive M9.5 implementation remains blocked until the locally validated corrected candidate is separately independently reviewed, is published only through the protected Git approval gates, and the exact published HEAD receives the required independent PASS.

## M9.4q post-adversarial local checkpoint - 2026-10-15

This is a **local, unstaged, unpublished** follow-up to the repository-first
independent M9.4q audit that returned `M94Q_AUDIT_GATE=BLOCKED`.
The earlier independent verdict remains historical and authoritative for that
earlier candidate; this checkpoint does not assert a fresh independent PASS.

Four confirmed follow-up defects are locally corrected:
- `M94Q-NEW-02`: oversized integer trade/execution quantities now fail the
  canonical result boundary in a controlled way, retaining strict integer
  type and positive-quantity semantics.
- `M94Q-NEW-04`: entry and non-null exit trade timestamps must match
  actually observed authoritative bar timestamps.
- `M94Q-NEW-05`: Study mean and median handle tested finite extremes without
  overflowing their intermediate arithmetic; subnormal precision is retained.
- `M94Q-NEW-06`: fresh SQLite job terminalization reads the durable
  cancellation request in its transaction and floors the shared terminal
  timestamp without changing legitimate SUCCEEDED/FAILED execution outcomes.

`KANASU_900168` verified 348 M9.4 tests across 21 modules, all 30 replayed
independent adversarial cases, and 1472 full Python tests, with no failures,
errors or skips. The exact source candidate comprised 15 modified tracked
files on `m9-v1-research-platform` at `0f679f9c24352dea46cff965f49eb4a53f5e9eed`;
none were staged. This documentation update is subsequent to that source
validation and does not alter tested production or test code.

Remaining gates: fresh repository-first independent pre-publication review,
separately approved protected Git operations if that review passes, and
independent exact published-HEAD PASS. Substantive M9.5 remains blocked.

## M9.4q financial-integrity remediation checkpoint - 2026-10-15

This is the latest LOCAL and UNPUBLISHED candidate checkpoint. The earlier
`KANASU_900168` count of 1472 full tests and 30 replayed cases is historical,
not the current gate. The subsequent independent Codex audit identified the
HIGH financial-reconciliation finding `M94Q-FINAL-01` and MEDIUM documentation
drift finding `M94Q-FINAL-02`. That prior audit was RED.

The candidate now reconciles authoritative flat-account cash against completed
net trade P&L and requires completed-exit evidence when holdings decrease.
Historical completed trades with nullable `exit_time` remain supported only
with compatible observed exit-bar diagnostics; a nullable timestamp does not
exempt a result from terminal settlement checks. Accepted M4 execution and
portfolio ownership have not changed.

- `KANASU_900227`: 1520/1520 full Python tests GREEN after compatible
  nullable-exit settlement correction.
- `KANASU_900228`: 1536/1536 full Python tests GREEN, including 16 additional
  nullable-exit adversarial cases and the existing financial controls.
- `KANASU_900229`: exact SHA256-verified original Codex reviewer source replay:
  15/15 financial counterexamples and 38/38 full reviewer cases GREEN,
  including persisted lookup, aggregation and registered Trial reuse.
- Original Codex reviewer source SHA256:
  `7dcc566765eb78e2948507c5ffcd93e37c5a48603a72e81a88463f56f1025fff`.
- Original reviewer replay manifest SHA256:
  `dfabdcc516507274cf3843b28090b0ff626efcb46fd6a7aaf78a7b96e053e2a4`.

The original reviewer replay was not a new independent verdict on the complete
revised candidate. A later fresh independent Codex audit did review the local
candidate and returned FAIL with four HIGH findings
(`M94Q-FRESH-INDEP-01` through `04`) and two MEDIUM findings (`05` and `06`).

Subsequent local remediation now has current-candidate GREEN evidence for
findings `01` through `05`: `KANASU_900286` passed 328 focused tests and all
52 current fresh-independent regression tests; `KANASU_900288` separately
confirmed the two-full-round-trip boundary (4 passed), manifest
initial-capital binding (4 passed), and numeric-overflow/reuse handling
(7 passed). These are remediation results, not an independent PASS.

`M94Q-FRESH-INDEP-06` was isolated as a documentation-only gap. The
implementation and permanent tests already establish that, for an unlinked
RUNNING ResearchJob, a durable pre-attempt cancellation request takes
precedence over a subsequent preparation failure: the ResearchJob and Trial
become CANCELLED, failure metadata is cleared, the event classification is
`running_cancellation_acknowledged`, and no RunAttempt is fabricated. The
documentation now explicitly traces that rule and the tests
`test_m94q_fresh_cancel_pre_attempt_request_wins` and
`test_m94q_fresh_cancel_pre_attempt_no_request_stays_failure`, while keeping
linked/in-flight computation semantics distinct.

The fresh independent FAIL remains authoritative until a new independent
review evaluates the corrected candidate. Publication, exact published-HEAD
review and M9.4q closure remain subject to their separate gates and human
approvals. `M94Q_AUDIT_GATE=BLOCKED`; M9.5 implementation remains BLOCKED.

## M9.4q synchronization review checkpoint - 2026-10-19

The current local M9.4q synchronization candidate remains **unstaged and
unpublished** on committed branch HEAD
`0f679f9c24352dea46cff965f49eb4a53f5e9eed`.

The independent synchronization review identified and corrected three
additional integrity defects after the earlier fresh-independent FAIL:

- `M94Q-SYNC-REVIEW-01`: canonical first-bar records may preserve a
  structurally valid pre-existing holding for compatibility, but the first
  record cannot carry execution settlement diagnostics because M4 next-bar
  execution cannot execute an order before that initial snapshot.
- `M94Q-SYNC-REVIEW-02`: REUSED Study aggregation now requires the durable
  `ResearchJob.reused_evidence_id` to equal the source successful
  `RunAttempt.evidence_id`, in addition to the existing attempt/result
  lineage checks.
- `M94Q-SYNC-REVIEW-03`: canonical Study aggregation now validates the
  immutable registered Trial-population proof before calculating any
  denominator or metric; durable Trial-row loss therefore fails closed
  instead of silently shrinking the Study denominator.

The synchronization checkpoint recorded 62/62 fresh-independent,
139/139 Study-aggregation, 23/23 queue/population, 471/471 explicit-focused
M9.4 and 1604/1604 complete Python tests. Those figures are retained as
historical evidence for that earlier candidate and are not the current
corrected-candidate validation. Independent adversarial lifecycle,
cancellation-race, exact-reuse/Study-authority and independent-account/numeric
reviews also pass on the current candidate.

These results are local corrective evidence, not publication or independent
release acceptance. Historical audit FAIL records and their dated test counts
remain historical evidence and are not rewritten.

`M94Q_AUDIT_GATE=BLOCKED` remains in force pending exact final-candidate
review, separately approved stage/commit/push operations, publication
verification, and a fresh independent audit of the exact published HEAD.

An eventual explicit independent PASS for the exact published M9.4 HEAD
authorizes **fresh M9.5 design only**. Earlier M9.5 Gate-A/design references
are historical context and do not control the next milestone. M9.5 must begin
as a fresh design exercise, and no M9.5 implementation is authorized until
that fresh design is separately accepted.

## M9.4q independent-review correction overlay (2026-10-19)

A fresh independent pre-publication review on 2026-10-19 rejected the then-current M9.4q synchronization candidate with two new blocking findings:

- `M94Q-IND-20261019-01` (**HIGH**) — canonical same-bar flat-to-flat evidence could claim an entry whose notional exceeded authoritative pre-bar cash and could then cross decoder, exact-reuse and Study-aggregation boundaries.
- `M94Q-IND-20261019-02` (**MEDIUM**) — queue progress and the public Trial-list read could silently shrink the fixed registered Trial denominator after durable Trial-row loss instead of validating the immutable registered-population proof.

The corrected local candidate now:

- enforces same-bar entry-notional affordability against authoritative pre-bar cash without changing M4 execution economics;
- retains valid affordable/real-M4 same-bar protective-exit evidence;
- validates registered Trial count and identity fingerprint from the same SQLite read snapshot used for authoritative queue-progress and public Trial-list reads;
- keeps the generic low-level `list_trials_for_revision()` persistence read unchanged for its established private/registration compatibility boundary;
- propagates population-proof corruption through application/HTTP reads as controlled failures;
- preserves exact reuse, aggregation, retry, cancellation/recovery, independent-account aggregation and prior M4-M9.3 authority.

Historical correction validation at the pre-FRESH-04 checkpoint:

- repository-wide `test_m94*.py` discovery: **541 passed across 23 files**;
- explicit preservation controls: **90 passed**;
- complete Python suite: **1665 passed**;
- `git diff --check`: PASS;
- staged files: zero.

Current gate after these local corrections:

- the corrections are **not published**;
- the M9.4q pre-publication gate remains **blocked pending a new fresh independent review of the exact corrected candidate**;
- staging, commit and push remain separately human-approved protected operations;
- the final M9.4 audit gate remains blocked until publication and an independent review of the exact published HEAD;
- M9.5 may begin only after that published M9.4 gate passes, and its next authority is **fresh design only**;
- M9.5 implementation is not authorized by this correction.

## M9.4q 2026-10-20 independent-review correction

The most recent fresh independent pre-publication review closed the previously
reviewed `M94Q-IND-20261019-01`, `M94Q-IND-20261019-02` and
`M94Q-SYNC-REVIEW-01/02/03` issues for that immutable candidate, but returned
FAIL on new MEDIUM finding `M94Q-IND-20261020-01`.

`M94Q-IND-20261020-01` showed that result-bearing Study aggregation could
accept an EXECUTED RunAttempt or REUSED source RunAttempt whose durable
`experiment_spec_id` no longer matched the immutable ExperimentSpec bound to
the Trial. The local correction now fails closed for that mismatch for both
completion kinds across core, application and HTTP reads.

The same correction cycle tightened `M94Q-IND-20261019-01`: same-bar funding
is an exact unlevered inequality. Any positive
`entry_notional - authoritative_pre_bar_cash` is invalid; the generic
financial reconciliation tolerance cannot authorize borrowing. A permanent
tiny-overspend regression now proves that boundary while exact-cash,
fee-envelope and accepted real-M4 controls remain valid.

Historical checkpoint local evidence was 541 repository-wide M9.4 tests across 23 files,
90 explicit preservation controls and 1665 complete Python tests, with clean
`git diff --check` and zero staged files.

This remains local corrective evidence only. The candidate is unstaged,
uncommitted and unpublished. A new immutable candidate and fresh independent
pre-publication PASS are required before any protected publication request.
Exact published M9.4 must subsequently independently PASS. Only then may M9.5
begin, and its next authority is fresh design only.

## M9.4q fresh independent-review follow-up - 2026-10-20

The preceding fresh independent pre-publication review independently re-ran the
accepted-scope validation and confirmed the previously reported
`M94Q-IND-20261019-01`, `M94Q-IND-20261019-02`,
`M94Q-IND-20261020-01`, and `M94Q-SYNC-REVIEW-01/02/03` cases closed for
the reviewed candidate, but returned FAIL on two new accepted-scope findings:

- `M94Q-FRESH-20261020-01` - the ordinary flat-to-long BUY evidence path
  could still admit a tiny positive entry-notional overspend because generic
  financial reconciliation tolerance was applied after computing
  `entry_notional`.
- `M94Q-FRESH-20261020-02` - multiple completed trades could claim the same
  observed BUY entry settlement even though exit settlement evidence was
  already uniquely consumed.

The local correction preserves the accepted M4 execution engine. Canonical
research-result validation now applies the exact unlevered predicate
`entry_notional <= authoritative_pre_entry_cash` to ordinary BUY evidence,
with no approximate-equality borrowing exception, and uniquely consumes
observed completed-trade entry settlements. Exact-cash BUY evidence and
distinct-entry completed trades remain valid.

Permanent direct/decoder RED-to-GREEN evidence is
`test_m94q_fresh_ordinary_buy_tiny_overspend_fails_closed`,
`test_m94q_fresh_ordinary_buy_exact_cash_control`,
`test_m94q_fresh_duplicate_entry_settlement_fails_closed`, and
`test_m94q_fresh_distinct_entry_settlements_control`.

Historical validation at that correction checkpoint was **541 repository-wide
M9.4 tests across 23 files, 90 preservation controls and 1665 complete Python
tests**, all passing with clean `git diff --check`. The M4 execution engine
remains byte-identical.

This is local corrective evidence only. The candidate remains unstaged,
uncommitted and unpublished. A new fresh independent pre-publication PASS is
required before any protected publication request. Stage, commit and push
remain separate human approvals. The exact published M9.4 HEAD must then
receive its own independent PASS. Only that published-head PASS authorizes
fresh M9.5 design; M9.5 implementation remains unauthorized until a fresh
M9.5 design is separately accepted.

## M9.4q FRESH-03 accepted-evidence aggregation correction - 2026-10-20

A subsequent fresh independent pre-publication review confirmed the prior
`M94Q-FRESH-20261020-01` and `M94Q-FRESH-20261020-02` corrections but found
new MEDIUM blocker `M94Q-FRESH-20261020-03`.

The defect was that a result-bearing EXECUTED or REUSED Trial could select a
real canonical `RunAttempt.result_artifact_id` for Study aggregation even when
the RunAttempt's already ACCEPTED ResearchEvidence still authorized a
different result. Exact-reuse lookup correctly rejected the damaged evidence,
but Study aggregation could still trust the substituted result.

The local correction keeps the accepted architecture and M4 execution engine
unchanged. Canonical result-bearing Study aggregation now loads the RunAttempt's
authoritative ResearchEvidence and requires all of the following before the
selected result becomes aggregation authority:

- the evidence exists and is `ACCEPTED`;
- evidence dataset, configuration and repository revision match the bound
  ExperimentSpec;
- `evidence.result_fingerprint` equals the selected canonical result artifact;
- the evidence references both the bound Backtest run manifest and selected
  result artifact;
- the referenced result and manifest remain canonical artifact kinds/schemas.

The durable evidence store is resolved from the same SQLite research database
owned by the catalog store, preserving the existing application constructor
contract. No M4 execution behavior or application public API contract changed.

Permanent isolated coverage contains 16 negative evidence-authority cases and
2 positive controls. Real persisted regression additionally covers
EXECUTED/REUSED across core Study aggregation, application aggregation and the
real FastAPI/ASGI HTTP route: 6 cases. The bounded integration selection passes
252 tests.

FRESH-03 checkpoint broad local validation was **541 repository-wide M9.4 tests across
23 files, 90 preservation controls and 1665 complete Python tests**, all
passing with clean `git diff --check`.

This remains local corrective evidence only. The candidate is unstaged,
uncommitted and unpublished. A new fresh independent pre-publication PASS is
required before any protected publication request. Stage, commit and push
remain separate human approvals. The exact published M9.4 HEAD must then
receive its own independent PASS. Only that published-head PASS authorizes
fresh M9.5 design; M9.5 implementation remains unauthorized until a fresh
M9.5 design is separately accepted.

## M9.4q FRESH-04 canonical evidence-database authority - 2026-10-20

A fresh independent pre-publication review of the post-FRESH-03 candidate
identified MEDIUM blocker `M94Q-FRESH-20261020-04`.

FRESH-03 correctly required every result-bearing EXECUTED or REUSED
Study-aggregation result to be authorized by actual ACCEPTED ResearchEvidence.
The remaining bypass was the optional `StudyAggregationService.evidence_store`
dependency: an ACCEPTED copy from a different SQLite database could be trusted
instead of contradictory evidence in the canonical research catalog database.

The local FRESH-04 correction preserves the accepted architecture:

- canonical persisted catalogs exposing `database_path` derive
  ResearchEvidence authority exclusively from that same catalog database;
- a foreign injected SQLite evidence store cannot override canonical evidence;
- explicit evidence-store injection remains only for lightweight/noncanonical
  catalogs without durable database authority;
- the application public contract and M4 execution engine remain unchanged.

Permanent real-SQLite regression coverage includes EXECUTED and REUSED foreign
database negative cases plus same-database positive controls.

FRESH-04 checkpoint authority was **4 FRESH-04 targeted / 18 FRESH-03 preservation /
256 bounded / 545 repository-wide M9.4 across 23 files / 90 preservation /
1669 complete Python**, all green with clean `git diff --check`. Those figures are historical FRESH-04 evidence after REVIEW-01.

The earlier **541 / 90 / 1665** figures remain historical FRESH-03 checkpoint
evidence and are not current closure evidence.

The candidate remains unstaged, uncommitted and unpublished. Fresh independent
pre-publication PASS is required before any protected publication request.
Stage, commit and push remain separate human approvals. The exact published
M9.4 HEAD must then receive its own independent PASS. Only that published-head
PASS authorizes fresh M9.5 design.

## M9.4q REVIEW-01 Trial identity integrity correction - 2026-10-20

A fresh independent pre-publication audit of the exact post-FRESH-04 candidate
returned `M94Q_AUDIT_GATE=BLOCKED` on a new accepted-scope integrity defect,
tracked here as `M94Q-REVIEW-01`.

The durable StudyRevision population proof correctly froze the finite surviving
`trial_id` denominator, but a persisted Trial identity-bearing field such as
`instrument_id` could be altered while retaining the original `trial_id`.
Because that `trial_id` was canonically derived from the StudyRevision,
instrument, membership episode, membership evidence and parameter
configuration, such a row no longer represented its registered immutable
identity even though an ID-only denominator proof could still match.

The local correction preserves the existing population-proof format. The
authoritative registered-population boundary now additionally recomputes each
persisted Trial's canonical content-addressed `trial_id` from its immutable
identity fields and fails closed on contradiction. Membership evidence artifact
identity is also required to remain consistent with its canonical evidence
fingerprint. The original REVIEW-01 description placed specific parameter/range
checks before registered-population validation. IND-01 supersedes that ordering:
the resolver consumes the authoritatively validated registered Trial before
deriving Trial-dependent plan values. Valid Trial identities retain their
ordinary parameter/range checks; downstream execution remains gated.

Permanent REVIEW-01 regression covers four cases: authoritative registered
population read, claimed execution before retrieval, EXECUTED aggregation and
REUSED aggregation. Current broad validation is **549 repository-wide M9.4
tests across 23 files, 90 preservation controls and 1673 complete Python
tests**, with clean `git diff --check`.

The prior **545 / 90 / 1669** result is historical FRESH-04 evidence. The prior
**541 / 90 / 1665** result remains historical FRESH-03 evidence. Neither is
current closure proof.

The corrected candidate remains unstaged, uncommitted and unpublished.
`M94Q_AUDIT_GATE=BLOCKED` pending a fresh independent review of this exact
corrected candidate. Stage, commit and push remain separate human approvals.
After publication, the exact published M9.4 HEAD must independently PASS before
M9.4 closes. Only that published-head PASS authorizes fresh M9.5 design; M9.5
implementation remains blocked until a fresh M9.5 design is separately accepted.


## M9.4q exact published-HEAD postpublication audit — 2026-10-21

Published, exact audited commit: `9f41a54c0c31985e4d33069401279586782c1858`
(parent `0f679f9c24352dea46cff965f49eb4a53f5e9eed`; tree
`561fdeefeea9fc64e56c5d2612da5537444cf0d3`).

Independent result: `M94Q_INDEPENDENT_VERDICT=FAIL`, `M95_GATE=BLOCKED`.
The published commit passed 1673 full Python tests and 549 M9.4 tests
across 23 files. Fresh reviewer-authored probes produced 14 passes,
9 failures against four accepted-scope integrity defects:

- **IND-01 (HIGH):** resolver and EXECUTED/REUSED aggregation can validate
  a different Trial snapshot than the consumed data.
- **IND-02 (HIGH):** persisted Trial identity corruption after plan
  resolution but during retrieval can precede a successful RunAttempt,
  exact reuse, or financial execution unless authority is transactionally checked.
- **IND-03 (MEDIUM):** Start may commit initial queue jobs for a corrupt
  Trial and then return an HTTP error when subsequent progress read fails.
- **IND-04 (MEDIUM):** canonical Trial-detail reads/HTTP route can emit a
  contradictory immutable registered identity.
- **DOC-01 (LOW):** published correction incorrectly described as
  unpublished in active status summaries.

The independent reviewer could not independently identify the reported
90-preservation-control selection; it did not refute the passing full-suite run.
Historical earlier local/unpublished checkpoint narratives elsewhere in this
document remain history and are not active publication status.

Implementation candidate: ChatGPT-authored unreferenced Git tree
`a4ac76fdce0d0c3a2f154b7ff94b971aaff88a81` (three corrected
production paths and two regression-test paths), based on the published
source tree. This is **NOT** a commit, branch update, run test or independent
acceptance. Later tree revisions require a new exact candidate identity.
Do not claim corrective PASS or M9.4q closure until real RED/GREEN, focused,
preservation and full-suite evidence, a new independent exact-candidate PASS,
and a verified exact published-HEAD PASS. No M9.5 work is authorized by
these preliminary corrections.


## M9.4q isolated GitHub-first development correction — 2026-10-21

Current development branch: `m94q-ind-authority-review`.
Code/test correction commit: `b8a9530000c68b11cc4ccb78a808d81b610f92e0`;
parent: `c173d7441278017181e0602d9cd59e7ef82cbed3`.
The branch began from published audited milestone commit
`9f41a54c0c31985e4d33069401279586782c1858`.
The milestone branch remains unchanged at that audited commit.

ChatGPT-authored changes target reviewer findings IND-01 through IND-04:
consume validated registered Trial snapshots, recheck identity inside the
RunAttempt, exact-reuse and terminalization authority transactions, reject
corrupt initial Start before durable queue writes, and verify Trial-detail
identity in one read transaction. Original population fingerprint format,
independent-account aggregation and earlier economic semantics are preserved.

Fresh added tests: 11 across a new identity-authority regression module and
executor-level retrieval/reuse/terminalization race coverage. After correcting
obsolete placeholder Trial-ID fixtures and expected error-order assertions,
**GitHub Actions run 39482178310** completed SUCCESS:
`1684 passed`, no failed tests, Python 3.11, in 16.43 seconds.
Earlier CI run 39481660667 reported `1679 passed, 5 failed`; it is superseded
for the corrected development commit and retained as RED/GREEN history.

The reported historical 90 preservation controls remain without an
independently identified exact selector; the complete 1684-test suite passed.
At this earlier development-validation checkpoint, independent Codex review
had not yet completed. The later exact-SHA audit of `e6002758` returned a
technical PASS, documented in the next section; this does not close M9.4q.
No milestone merge, integration or publication has occurred. M9.5 remains
blocked pending human-approved integration and exact published-HEAD PASS.


## M9.4q independent development-candidate audit outcome — 2026-10-21

**Reviewer target:** branch `m94q-ind-authority-review`, commit
`e6002758f22e0bb07d0886dcc1603eba21e6e501`,
tree `3a9c79aea390da70b4b242f7819b0f58ef76a40e`.
Published milestone branch remains at independently failed `9f41a54c`.

**Independent technical verdict: PASS** at the reviewed development SHA.
IND-01 validated snapshot consistency, IND-02 fresh/reuse/terminal authority,
IND-03 atomic Start, and IND-04 coherent Trial detail were each **CLOSED**.
No new accepted-scope runtime blocker was found. The external auditor observed:

- 1684 complete repository Python tests passed (Python 3.12), including
  560 M9.4 tests across 24 files;
- 23 prior and 99 extended reviewer-authored probes passed (122 total);
- GitHub Actions run `39482590794` (Python 3.11), 1684 passed at
  this exact SHA;
- nonblocking LOW `M94Q-COR-DOC-01`: stale traceability, test header
  and decision history; one trailing space on `ROADMAP.md` line 704;
- the separate historical 90 preservation controls were not identified as
  an independently runnable selector.

A follow-up documentation-only correction is authorized on the isolated
development branch and does not change the reviewed runtime implementation.
Historical checkpoints elsewhere remain historical. The final candidate SHA
after documentation cleanup must be mechanically checked, and its exact
identity must be verified before any acceptance request.

**No M9.4q closure or M9.5 authorization is implied by this PASS.**
Human approval is still required for milestone integration, followed by
a separate independent PASS on the exact published milestone HEAD.
## Current published-head reconciliation — 2026-10-21

**Historical checkpoint:** The findings below describe the `929db5d6` published-head audit of 2026-10-21 and retain their original scope and meaning. See the [current dashboard](#current-dashboard) for the preparation baseline and remaining gates. The historical `NOT_VERIFIED` approval result is unchanged.

**Audited source baseline:** branch `m9-v1-research-platform`,
commit `929db5d6b207d172b66cb3b38ae9b0f617f8ce0a`,
tree `d5e7e66c68158a4abe1293210c6510bb7fc47077`.
Its direct parent is `e6002758f22e0bb07d0886dcc1603eba21e6e501`.
The correction is integrated into the published branch; its historical
human integration/protected-operation approvals remain **NOT_VERIFIED**.

The published commit changed six documentation files and only the opening
module docstring of `tests/research/test_m94q_ind_identity_authority.py`.
Production subtrees and the remaining test-module source are unchanged.
Technical PASS is a bounded carry-forward from the independently reviewed
parent, supported by those checks and exact published-SHA
[CI run 39527603226](https://github.com/kanasu-01/kanasu-trading-system/actions/runs/39527603226):
Python 3.11, **1684 collected and passed**.

Parent [CI run 39482590794](https://github.com/kanasu-01/kanasu-trading-system/actions/runs/39482590794),
the reported Python 3.12 reviewer run, 560 M9.4 cases across 24 modules and
122 reviewer-authored probes belong to `e6002758`; they are not claimed as
new reviewer runs at `929db5d6`. The historical 90-control selector remains
independently unidentified.

| Audit axis at the source baseline | Disposition |
|---|---|
| Technical | PASS by verified carry-forward |
| Documentation | FAIL: `M94Q-PH-DOC-01` publication/status contradictions and `M94Q-PH-DOC-02` superseded validation-order wording |
| Human integration approval | `M94Q-PH-EVID-01 = NOT_VERIFIED`; unavailable records are not proof of absent or unauthorized approval |
| Overall published-head gate | `M94Q_PUBLISHED_HEAD_GATE=VERIFIED_FAIL` |

M9.4q is not DONE/CLOSED. M9.5 Draft v0.3 has a separately reported design-level
PASS WITH NONBLOCKING OBSERVATIONS; formal admission and implementation remain
blocked. Original attributable approvals must be supplied and assessed.

This documentation reconciliation grants no retrospective approval, repository
edit authority or Git authority. A later separately approved documentation
commit will have a different, presently unknown SHA. Its technical and
documentation verdicts require fresh independent exact-published-HEAD review;
this source-baseline audit does not automatically cover it. Required human
approval of the exact diff, applied-diff verification, and separately authorized
stage, commit, push and integration remain distinct gates.


## M9.4q consolidated stabilization candidate — 2026-10-28

**Historical pre-publication preparation checkpoint; superseded for current publication/source status by the verified checkpoint below.** At this checkpoint the state was locally implemented/validated in an isolated cloud copy; UNPUBLISHED; M9.4q OPEN/BLOCKED. Source baseline is GitHub branch `m9-v1-research-platform`, `c6e2d3cb199f9bbed606e89f3644f40950aee46c` (366 original file hashes verified). This section describes the proposed resulting documentation, not a new published commit.

BEHAVIOR IMPACT: CHANGED — manifest-bound research acceptance and fresh-result acceptance only. RO-01 requires exact zero opening position while retaining generic legacy decoding; CS-001 binds disabled-brokerage cash/transaction-cost evidence using recorded, potentially slipped fills; CS-002 binds completed-trade symbols to the manifest; CS-003 validates a private fresh-result snapshot before accepted success. Existing reuse and canonical EXECUTED/REUSED aggregation already cross the shared boundary. No financial engine, schema, fingerprint, queue or API contract changed.

The new regressions include both tiny-mark RO-01 cases, canonical/generic compatibility, missing/numeric authority, disabled-fee/symbol contradictions, durable EXECUTED/REUSED rejection and valid fresh fallback, standalone/nonexact and claimed failure, cancellation, explicit retry, failed-transaction rollback/recovery, private-result mutation and real M4 controls. One pre-existing API projection fixture was made financially coherent while preserving its assertions distinguishing realized P&L (240) from marked account P&L (250).

VALIDATION: Python 3.12.14 on Linux; 66 focused cases, 273 affected-module tests, 609 M9.4 cases across 24 modules and 1,750 full Python cases passed, with no failures/errors/skips. The full run reported 457 existing `datetime.utcnow()` deprecation warnings (two additional occurrences from new real-engine controls); CS-004 remains deferred. The initial baseline RED run recorded 48 failing/10 passing new cases. Exact commands, log hashes and candidate source identity are provided with the approval packet; no new GitHub CI or independent PASS is claimed.

CODE/TEST IDENTITY: `4eea409c1dc68f9c0da65be1ac3f46159300d9076a4db83cc63c6f4e4cc0042d` — SHA-256 of sorted changed Python paths, NUL, each file's SHA-256, newline. It is a content identity, not a Git commit. See [Validation Plan](validation/VALIDATION_PLAN.md#m94q-consolidated-stabilization-validation--2026-10-28).

GOVERNANCE: R004 acceptance and unchanged RO-01 V002 approval are preserved. The handoff attributes original Library V10 retrieval to ChatGPT; Codex has not independently retrieved that authority. Required formal source verification remains unresolved without blocking authorized isolated preparation. Historical protected-operation approval records, original audit-report F06 and the unidentified historical 90-control selector are not fabricated. A corrected technical PASS cannot retrospectively authorize Git history. No SOP amendment, M9.4q closure or M9.5 admission is implied.


## M9.4q verified implementation publication — 2026-10-28

Implementation commit `4c1067fac6aec337ec10ac6e63409482ca649d15` has parent `c6e2d3cb199f9bbed606e89f3644f40950aee46c` and tree `388bfd51b03f25ea8c1a90a1d138564166c81c20`. The guarded, non-force update of `m9-v1-research-platform` was separately authorized and verified. All 367 published file paths, modes and blob identities match the approved twelve-file candidate. Its combined diff SHA-256 is `f02049f2de6351ffad16ea1d59e225b8c2f1c933917182f4dde8edc383fe2802`. The implementation, regressions and complete unchanged specification archive are preserved in this same commit.

The prior independent candidate review passed 1,750 repository tests and 32 reviewer-authored adversarial checks; these are independently executed candidate results, not invented CI counts or a new run for this documentation update. GitHub CI run [40700668246](https://github.com/kanasu-01/kanasu-trading-system/actions/runs/40700668246) completed SUCCESS for the actual implementing SHA, including its test job and Run tests step. Independent published-state checking verified technical/specification/approved-content conformity, the full tree, source identity and CI; it identified the stale current dashboard/source/approval wording corrected by this documentation synchronization. Overall published-state acceptance requires review of the actual synchronized final documentation, followed by Human Approval 3. Neither is claimed in advance here.

The owner explicitly designated the GitHub SOP as authoritative. Independent live-source verification identified unchanged SOP blob `19b307a8e9bd607a72988402bcb24c57ba51f898`, SHA-256 `3ddfc8f38a84962c9cf9cbec94a57c52b36002b1029994c293a888d91139a2d5`. This resolves the current source-access gate prospectively; no original Library retrieval or historical Git authorization is invented. R004 and unchanged RO-01 V002 approvals stand. Missing historical protected-operation approvals, original audit-report F06 and the unidentified historical 90-control selector retain NOT_VERIFIED status. M9.4q remains OPEN/BLOCKED and M9.5 is not admitted.


## M9.4q closure governance publication checkpoint — 2026-10-28

Accepted technical baseline: `87d740d9d5558821088d8095fd4cf59dcb81bee6`, implementing commit `4c1067fac6aec337ec10ac6e63409482ca649d15`. Final technical published-state Review 2 PASS report SHA-256: `2bc02fbfe55448ca8d5e919fded33e0ac2d3d4e8c4851e587d495b8e871f1ea0`; attributable Human Approval 3 record SHA-256: `b75bb130b173fd2f098fee08b6f9a89e4863625cd3b94c6da00a20a98389c09c`. Actual final-SHA CI run 40703344719 succeeded. The earlier preparation/publication checkpoints above retain their original pending-gate statements as historical evidence; this section records the subsequent completion of those correction-package gates.

The owner approved the complete proposed Governance section 7.1 and explicitly approved its exact unified comparison as the alternative change-highlighting mechanism. Independent governance Review 1 formally passed after resolution of that sole presentation gate; final addendum SHA-256: `504b39fa86737839533f2d6acefff9283434c6e71cba9fa7d90ecc255ad7f9a7`. Original Review 1 presentation BLOCKED report remains unchanged. The complete approved subsection, original section 7, exact comparison, approvals and independent review evidence are preserved together in the [Governance review record](governance/reviews/M94Q_SECTION7_1_REVIEW_RECORD.md).

This publication checkpoint preserves M9.4q OPEN/BLOCKED until actual approved governance publication/read-back, actual-state Review 2 and explicit final human milestone acceptance have completed. The future governing publication commit is the first commit introducing that review record together with the exact approved Governance section 7.1 and synchronized status/traceability/validation records. Its actual SHA and activation/read-back, review and human acceptance outcomes must be recorded in publication evidence when known; no future SHA or acceptance is invented here.

Historical protected-operation approvals and original audit-report F06 stay NOT_VERIFIED; the historical 90-control selector remains unidentified. The approved prospective basis neither asserts those historical checks passed nor waives known unauthorized actions or higher-level controls. CS-004 remains nonblocking deferred work. No production/test/frozen technical specification, Global SOP, dependency, strategy or financial-engine change is included. M9.5 admission and implementation remain separate and unauthorized.
