# Kanasu Deferred Work

## Purpose

This ledger preserves material technical issues that are understood but intentionally outside the active task. An item remains visible until it is resolved, cancelled or superseded with evidence. Product ideas belong in the [Product Vision](../PRODUCT_VISION.md) or [Roadmap](ROADMAP.md); architecture choices belong in [Decisions](../architecture/DECISIONS.md).

Existing identifiers are permanent.

## DW-001 — Equity-Based Drawdown

**Status:** OPEN
**Target:** M4.5 / M5 risk and research validity; required before V2.

Account-level net realized trade contribution was corrected in M2.3. Daily and weekly drawdown controls still aggregate recorded closed-trade percentages rather than being defined from actual account equity through time, including unrealized P&L where appropriate.

Required work: define the intended daily/weekly denominator, treatment of realized and unrealized changes, session boundaries, reset semantics, and deterministic validation cases.

## DW-002 — P&L Percentage Accounting

**Status:** PARTIALLY ADDRESSED
**Target:** M4.4 / M5.

M2 established explicit fill/cost ownership, gross and net monetary trade P&L, and account-level net P&L input to DrawdownRiskManager. `Trade.pnl_pct` remains instrument-price return; it is not gross or net monetary P&L and must not substitute for account/equity return.

M4.4 implements and validates the Backtest account-performance/reporting portion through a result-aware metric path. `Trade.pnl_pct` retains instrument fill-to-fill return meaning; completed-trade gross and net outcomes remain monetary P&L; and authoritative Backtest account P&L, account return and maximum drawdown derive from recorded equity, including transaction-cost and final unrealized effects.

**M4.4 evidence:** implementation commit `7102859ecb80bf932a780825f10634fd36cb0a9d Implement M4.4 account performance metrics`; focused metric/reporting, compatibility and regression validation passed; independent full suite 364 passed in 6.86s.

Remaining work: M5 must migrate the bounded legacy WFA trade-only metric path and establish WFA account-metric validity. No unnecessary gross-trade-return or net-trade-return percentage concepts are required. DW-002 therefore remains PARTIALLY ADDRESSED rather than resolved.

## DW-003 — Portfolio Accounting Consistency

**Status:** RESOLVED

**Resolution scope:** M1 authoritative simulated backtest/execution path.
**Evidence:** commit ffc8cc6 and the portfolio/execution/backtest regression tests.

PortfolioManager owns simulated cash, position value, equity and P&L; PositionBook owns open Position objects; TradeExecutionEngine uses the authoritative lifecycle; BacktestEngine reports the execution portfolio snapshot.

This resolution does not claim paper API/runtime integration, broker reconciliation or multi-symbol portfolio validation. Those have separate items.

## DW-004 — Paper Trading Runtime Validation

**Status:** OPEN
**Target:** V1 M6/M7.

The current principal paper path uses CSV replay, while API paper support manages session metadata without starting the complete PaperRuntime. Real live-market-data paper operation, truthful lifecycle state, authoritative snapshots, journals, failure handling, stop behavior and recovery policy remain to be implemented and validated.

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

**Status:** OPEN
**Target:** M5.

The expanding-window generator can repeat a window indefinitely because the advancing cursor does not affect the expanding train start/end calculation after the first valid window.

Required work: write finite deterministic rolling/expanding-window contracts, repair the generator, and test boundaries and termination without changing research policy implicitly.

## DW-008 — WFA Configuration, Economics and Account Metrics

**Status:** OPEN
**Target:** M5.

Optimizer/runner paths create backtests with hardcoded capital and fresh runtime defaults. Some scoring and drawdown calculations use instrument Trade.pnl_pct or synthetic compounded trade returns instead of authoritative account outcomes.

Required work: propagate the effective capital, execution/risk configuration and dataset identity; define account-valid optimization metrics; define window overlap/equity-stitching semantics; preserve per-window evidence.

## DW-009 — Strategy and Execution Position-State Agreement

**Status:** PARTIALLY RESOLVED
**Target:** M4.2 before strategy conclusions; M7 before paper acceptance.

A strategy can change its local position-open state after emitting BUY without a complete response for risk rejection, affordability rejection or forced stop exit. Strategy state can then disagree with the execution portfolio.

M4.2 resolves the validated Backtest/`SMACrossOverStrategy` execution-feedback and state-convergence scope. The typed ordered AD-017 contract covers accepted and rejected entries, strategy and protective exits, explicit rejection reasons, contradictory-state failures and authoritative outcome ordering without changing PortfolioManager accounting ownership.

**Evidence:** implementation commit `770d3a5 Implement M4.2 execution feedback contract`; focused execution/backtest validation 26 passed; independent full suite 323 passed.

DW-009 remains partially resolved because paper-runtime feedback/state convergence is still required before M7 acceptance. PivotBoss and other unvalidated strategy-specific state contracts also remain outside the M4.2 resolution claim.

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

**Status:** OPEN
**Target:** M7/M8.

The backtest run API returns a fixed mock result. Paper API endpoints create/session-stop metadata but do not own the real PaperRuntime. The frontend therefore cannot yet serve as a validated research/paper control plane.

Required work: replace placeholders through bounded vertical slices using real jobs and authoritative snapshots; expose truthful loading, running, stopped and failed states.

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
**Target:** M6/M7 broker/live-data and paper-session work; required before V1 real-market-data paper acceptance. Reassess and extend for V2 live execution.

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

## Maintenance

New entries use the next available DW identifier after inspecting this ledger. Group related symptoms by root cause where practical. A resolution records the exact scope, evidence and related milestone/decision; it does not erase history.
