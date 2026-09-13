# Kanasu Deferred Work

## Purpose

This ledger preserves material technical issues that are understood but intentionally outside the active task. An item remains visible until it is resolved, cancelled or superseded with evidence. Product ideas belong in the [Product Vision](../PRODUCT_VISION.md) or [Roadmap](ROADMAP.md); architecture choices belong in [Decisions](../architecture/DECISIONS.md).

Existing identifiers are permanent.

## DW-001 — Equity-Based Drawdown

**Status:** OPEN
**Target:** M4/M5 risk and research validity; required before V2.

Account-level net realized trade contribution was corrected in M2.3. Daily and weekly drawdown controls still aggregate recorded closed-trade percentages rather than being defined from actual account equity through time, including unrealized P&L where appropriate.

Required work: define the intended daily/weekly denominator, treatment of realized and unrealized changes, session boundaries, reset semantics, and deterministic validation cases.

## DW-002 — P&L Percentage Accounting

**Status:** PARTIALLY ADDRESSED
**Target:** M4/M5.

M2 established explicit fill/cost ownership, monetary gross/net P&L, and account-level net P&L input to DrawdownRiskManager. Trade.pnl_pct remains an instrument-price percentage return.

Required work: preserve the instrument meaning where useful while defining gross trade return, net trade return and account/equity return for reporting and research. Instrument pnl_pct must not substitute for an account-return metric.

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

**Status:** OPEN
**Target:** M4 before strategy conclusions; M7 before paper acceptance.

A strategy can change its local position-open state after emitting BUY without a complete response for risk rejection, affordability rejection or forced stop exit. Strategy state can then disagree with the execution portfolio.

Required work: define a small execution-feedback/state-authority contract and test accepted entry, rejected entry, strategy exit and forced exit.

## DW-010 — SQLite Timestamp and Range-Bound Compatibility

**Status:** RESOLVED

**Resolution scope:** M3.6c local historical storage/retrieval timestamp compatibility.
**Evidence:** AD-013; implementation commit `1c4a877`; M3.6c timestamp/storage regression tests.

M3.6c removed lexical ISO-string ordering/filtering as the chronological authority. Persisted timestamps are parsed and compared using Python datetime semantics. Incompatible naive/aware state is rejected explicitly; differing aware offsets remain supported; timestamp representations are preserved without UTC normalization; and aware timestamps representing the same instant define one candle identity across differing offsets.

This resolution does not claim migration or automatic repair of old invalid databases, and it does not claim storage scalability has been solved. Those concerns are recorded in DW-014.

## DW-011 — Offline Runtime Requires Broker Login

**Status:** OPEN
**Target:** M3.7.

Main constructs/authenticates a broker before selecting a mode, so a request satisfiable from local data is not fully local.

Required work: introduce an explicit historical source policy and lazy provider construction after local-first retrieval contracts are complete. See proposed AD-009.

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

## Maintenance

New entries use the next available DW identifier after inspecting this ledger. Group related symptoms by root cause where practical. A resolution records the exact scope, evidence and related milestone/decision; it does not erase history.
