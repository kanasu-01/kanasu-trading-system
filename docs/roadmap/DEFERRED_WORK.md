# Kanasu Deferred Work

## Purpose

This ledger preserves material technical issues that are understood but intentionally outside the active task. An item remains visible until it is resolved, cancelled or superseded with evidence. Product ideas belong in the [Product Vision](../PRODUCT_VISION.md) or [Roadmap](ROADMAP.md); architecture choices belong in [Decisions](../architecture/DECISIONS.md).

Existing identifiers are permanent.

## DW-001 — Equity-Based Drawdown

**Status:** PARTIALLY ADDRESSED
**Target:** V2 broker/live risk policy; V1 research/paper shared-engine behavior accepted.

M4.5 established authoritative-equity daily/weekly entry guards for canonical Backtest. M5 subsequently propagated the accepted economic/risk configuration through WFA and validated account-based research outcomes.

M7 paper processing uses the shared `TradeExecutionEngine` with effective runtime risk/economic policy rather than maintaining a separate fixed-capital paper sizing implementation.

The remaining concern is future real-money broker/live risk authority: exposure, broker/account reconciliation and operational safeguards require separate V2 validation.

## DW-002 — P&L Percentage Accounting

**Status:** RESOLVED
**Resolution scope:** V1 Backtest/WFA research metrics.

M2 established explicit fill/cost ownership and monetary P&L. M4.4 separated instrument return from authoritative account/equity return. M5 migrated WFA metrics, stitching and verdict semantics onto the accepted account-valid model.

`Trade.pnl_pct` intentionally remains instrument fill-to-fill return. Gross/net completed-trade outcomes remain monetary P&L, while account return and drawdown derive from authoritative equity.

## DW-003 — Portfolio Accounting Consistency

**Status:** RESOLVED

**Resolution scope:** M1 authoritative simulated backtest/execution path.
**Evidence:** commit ffc8cc6 and the portfolio/execution/backtest regression tests.

PortfolioManager owns simulated cash, position value, equity and P&L; PositionBook owns open Position objects; TradeExecutionEngine uses the authoritative lifecycle; BacktestEngine reports the execution portfolio snapshot.

This resolution does not claim paper API/runtime integration, broker reconciliation or multi-symbol portfolio validation. Those have separate items.

## DW-004 — Paper Trading Runtime Validation

**Status:** RESOLVED AT ACCEPTED M7 SCOPE

M6 established AngelOne live market data. M7 implemented real-data paper operation with simulated execution and authoritative PortfolioManager state, causal next-bar execution, provider supervision, reconnect/reconciliation, truthful terminal state, unique session/journal identity and authoritative snapshots.

Final accepted baseline: `7dd8e34`. Final local regression: 725 passed. GitHub Actions Run 92 succeeded.

This resolution does not claim API/frontend ownership, process-restart recovery or real-money execution. Those remain under M8/M9, DW-013/DW-015 or V2 as applicable.

See [Paper Runtime](../design/PAPER_RUNTIME.md).
## DW-005 — Live Trading

**Status:** DEFERRED TO V2
**Consequence when active:** VERY HIGH.

Real-money execution is outside V1. V2 requires broker order lifecycle, stable identity/idempotency, cancellation/partial fills, reconciliation, restart recovery, cash/position/order checks, operational safety, restricted rollout, and applicable broker/exchange/regulatory acceptance.

Existing adapter or dormant engine code does not satisfy this release gate.

## DW-006 — Multi-Symbol Portfolio

**Status:** DEFERRED
**Target:** V3+ candidate scope.

PositionBook structure alone does not establish multi-symbol capital allocation, synchronized data, aggregate exposure, correlation, portfolio drawdown or risk semantics. Preserve the single-symbol boundary until those contracts are designed and validated.

## DW-007 — WFA Expanding-Window Termination

**Status:** RESOLVED
**Resolution scope:** M5 WFA validity.

M5 made expanding/rolling window generation finite and later hardened warm-up, strategy-parameter and numeric boundary behavior.

Final accepted M5 baseline: `7d74ea2`.

## DW-008 — WFA Configuration, Economics and Account Metrics

**Status:** RESOLVED
**Resolution scope:** M5 WFA validity.

M5 propagated effective configuration/economics, established account-valid metrics, hardened equity stitching and verdict semantics, integrated the accepted WFA contract, and later hardened precision, warm-up, strategy parameters and numeric boundaries.

Final accepted M5 baseline: `7d74ea2`.

## DW-009 — Strategy and Execution Position-State Agreement

**Status:** RESOLVED AT VALIDATED REFERENCE-STRATEGY SCOPE
**Resolution scope:** `SMACrossOverStrategy` across accepted Backtest and paper paths.

M4.2 established typed ordered execution feedback and authoritative state convergence for Backtest. M7 paper processing delivers authoritative execution feedback before the next completed-candle decision and uses the same execution/portfolio authority.

M7 causal-validity validation covers accepted entry feedback, duplicate/non-causal next-open protection, protective exits and ordering relative to subsequent strategy decisions. Pending intent is invalidated across provider gaps before reconciliation.

PivotBoss and other independently unvalidated strategy-specific state contracts remain outside this resolution.

## DW-010 — SQLite Timestamp and Range-Bound Compatibility

**Status:** RESOLVED

**Resolution scope:** M3.6c local historical storage/retrieval timestamp compatibility.
**Evidence:** AD-013; implementation commit `1c4a877`; M3.6c timestamp/storage regression tests.

M3.6c removed lexical ISO-string ordering/filtering as the chronological authority. Persisted timestamps are parsed and compared using Python datetime semantics. Incompatible naive/aware state is rejected explicitly; differing aware offsets remain supported; timestamp representations are preserved without UTC normalization; and aware timestamps representing the same instant define one candle identity across differing offsets.

This resolution does not claim migration or automatic repair of old invalid databases, and it does not claim storage scalability has been solved. Those concerns are recorded in DW-014.

## DW-011 — Offline Runtime Requires Broker Login

**Status:** RESOLVED
**Target:** M3.7.

M3.7c moved research-runtime broker construction and authentication behind the lazy historical-provider factory. Structurally, `LOCAL_ONLY` and fully covered `LOCAL_FIRST` requests should therefore be capable of running without credentials, broker construction, login, or provider access.

That structural change alone did not resolve DW-011. M3.7d subsequently proved that both Backtest and WFA execute through the actual runtime/source-composition boundary without credential loading, broker construction, login, or provider access when `LOCAL_ONLY` or fully covered `LOCAL_FIRST` does not require external capability.

**Resolution scope:** M3.7 historical source policy/runtime integration.

**Evidence:** M3.7d design baseline `0726b148`; M3.7d implementation and validation `7f968843`; focused integration 17 passed; full suite 240 passed. See accepted AD-009.

## DW-012 — Legacy Replay, Export and CSVBroker Contracts

**Status:** OPEN
**Target:** Triage during M3.7/M3.8 or the relevant replay/export milestone.

Legacy launchers and adapters retain stale constructor/entity assumptions. Historical CSV export loses timestamp offset/microseconds and constructs HistoricalFeed with an outdated signature. CSVBroker does not conform to current Candle/BaseBroker contracts. BarByBarReplay does not provide a complete current replay workflow.

Required work: decide which public paths remain supported, write compatibility tests for retained paths, and retire or repair them without using them to bypass canonical data boundaries.

## DW-013 — API Placeholders and Paper Runtime Disconnection

**Status:** RESOLVED AT M8 APPLICATION SCOPE
**Resolution scope:** M8 authoritative Backtest/Paper application boundary.

M8.2 replaced the fixed Backtest API result with the real historical-source → validated strategy → `BacktestEngine` path and returns the actual `BacktestResult.session_id`, result-aware metrics, equity and completed trades.

M8.3 replaced metadata-only paper ownership with one process-local application-owned authoritative `PaperTradingSession` / `LivePaperRuntime` handle, synchronized status, real runtime stop/worker termination, runtime-failure propagation and retained terminal snapshots.

M8.4 connected the frontend to these authoritative contracts, removed machine-specific API configuration and presents backend-owned Backtest/Paper state rather than reconstructing account authority in React.

M8.5 integration and closure validation passes 58 API/application tests, 792 full Python tests and 17 frontend tests. Production build, lint and responsive desktop/mobile browser smoke pass. M8.5c required only a bounded frontend-shell correction for responsive composition plus truthful Portfolio coming-soon wording; it did not change trading/runtime/broker authority.

This resolution does not claim process-restart recovery, reusable broker-session/authentication lifecycle, real-money execution, legacy Replay/export repair or multi-symbol portfolio semantics. Those remain separately scoped.
## DW-014 — SQLite Chronology Indexing and Legacy Timestamp-State Migration

**Status:** DEFERRED
**Target:** M3.8 or later storage hardening; required before scale makes dataset scans operationally significant.

M3.6c deliberately uses correctness-first dataset scans to compare parsed datetime identity and timezone awareness. This is correct for the current milestone but may become inefficient for very large datasets.

Existing databases that already contain invalid mixed-awareness state or historical cross-offset duplicate logical timestamps are rejected rather than automatically repaired.

Future work, if required, should define:

- a chronology-safe persisted indexing/key strategy;
- explicit schema migration;
- a legacy invalid-state detection and repair policy;
- backward-compatibility tests; and
- performance evidence.

This is not a current M3.6 correctness blocker.

M3.8 baselining does not automatically pull this work into implementation. Correctness-first historical dataset scans remain acceptable for the M3.8 parity scope unless focused evidence shows that they prevent M3.8 acceptance. DW-014 remains DEFERRED and requires separate scope and authorization.

## DW-015 — Broker Session and Authentication Lifecycle

**Status:** OPEN
**Target:** M8/M9 V1 operational-hardening disposition; reassess and extend for V2 live execution.

Current broker authentication is not yet a reusable session lifecycle. When `create_angelone_broker()` is invoked it constructs a new broker and calls `login()` eagerly. `AngelOneBroker` tracks `_logged_in` only within the current broker object/process, but `login()` does not first determine whether an existing authenticated session is still usable. Separate program runs also do not currently reuse or validate a previously created broker session.

Required future behavior:

- when broker capability is required, first determine whether a usable authenticated broker session already exists;
- if the existing session is valid, reuse it and do not perform another login;
- if no usable session exists, perform authentication;
- if a session exists but is expired or invalid, refresh it when the broker supports safe refresh, otherwise re-authenticate explicitly;
- historical data, live market data, account queries and eventually order execution should reuse the appropriate shared authenticated broker lifecycle rather than independently creating unnecessary sessions;
- distinguish process-local broker reuse from any optional persistence or reuse across application restarts;
- define safe token/session storage, expiry handling, refresh ownership, logout/cleanup, concurrency and failure semantics;
- do not log credentials, TOTP secrets, access tokens, refresh tokens or other sensitive authentication material;
- keep the lifecycle broker-agnostic so AngelOne is the first adapter, not the architectural owner of the policy; and
- add deterministic tests for already-authenticated reuse, initial login, expired/invalid-session recovery, authentication failure and concurrent or repeated capability requests.

Do not implement this behavior now.

## DW-016 — AngelOne Historical Negative-Volume Anomaly

**Status:** DEFERRED
**Target:** Future broker/historical-provider hardening under separately approved scope.

During M8.4 broker-backed historical verification, one raw AngelOne 5-minute historical row was observed with negative volume:

- timestamp: `2024-03-02T11:15:00+05:30`
- OHLC: `1497.0 / 1497.0 / 1497.0 / 1497.0`
- volume: `-444538`

The canonical `Candle` contract correctly rejects negative volume. The current AngelOne adapter passes the provider volume through unchanged, so a request containing this row fails rather than silently repairing invalid canonical data.

A read-only scan performed during diagnosis examined 92,465 5-minute rows and 30,842 15-minute rows. The 5-minute scan contained one negative-volume row; the 15-minute scan contained none. Across 123,307 scanned rows, the observed negative-volume count was one.

The issue was explicitly deferred during M8.4. No normalization, clamping, skipping, quarantine or provider-specific repair is authorized by this entry.

Future work, if approved, must define the provider-boundary policy, preserve the canonical non-negative-volume invariant, define retrieval/coverage behavior when a raw provider row is rejected or quarantined, and add deterministic regression evidence without weakening `Candle` validation.

## Maintenance

New entries use the next available DW identifier after inspecting this ledger. Group related symptoms by root cause where practical. A resolution records the exact scope, evidence and related milestone/decision; it does not erase history.
