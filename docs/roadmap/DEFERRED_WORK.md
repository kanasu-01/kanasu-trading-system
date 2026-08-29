# Kanasu — Deferred Work

This document records work that has been identified but intentionally
postponed.

Items must not disappear simply because development moves to another
task.

---

## DW-001 — Equity-Based Drawdown

Status: Deferred

Current approach:
Daily and weekly drawdown are currently based on recorded trade P&L.

Required future work:
Evaluate and implement drawdown based on actual portfolio equity,
including unrealized P&L where appropriate.

Reason deferred:
Keep the current MVP implementation simple while validating the
basic risk-control mechanism.

Revisit:
Before Live Trading.

Priority:
HIGH


---

## DW-002 — P&L Percentage Accounting

Status: Deferred / Current Focus

Issue:
Trade P&L percentage and monetary P&L need to be defined consistently,
particularly when transaction costs and slippage are included.

Required future work:
Establish clear gross P&L, net P&L, gross return percentage and
net return percentage definitions.

Revisit:
Immediately.

Priority:
HIGH


---

## DW-003 — Portfolio Accounting Consistency

Status: Deferred

Issue:
Portfolio state and execution state require further validation to
ensure there is one authoritative representation of capital,
positions, realized P&L, unrealized P&L and equity.

Required future work:
Review PortfolioManager and BacktestEngine integration.

Revisit:
Before advanced performance analytics.

Priority:
HIGH


---

## DW-004 — Paper Trading Runtime Validation

Status: Deferred

Issue:
The paper-trading runtime architecture exists but requires further
validation with the complete runtime, API and frontend flow.

Required future work:
Validate:
- session lifecycle
- feed
- strategy runner
- execution engine
- portfolio state
- snapshots
- API
- frontend
- stop/start behaviour

Revisit:
After core execution/risk validation.

Priority:
HIGH


---

## DW-005 — Live Trading

Status: Deferred

Current state:
LIVE mode is not implemented.

Required future work:
Build live broker execution only after paper trading has been
validated.

Important:
Live Trading must reuse the validated market-data, strategy,
execution, risk, portfolio, session and monitoring architecture.

Revisit:
After Paper Trading MVP is stable.

Priority:
VERY HIGH


---

## DW-006 — Multi-Symbol Portfolio

Status: Deferred

Current state:
PositionBook has a structure that can support multiple symbols,
but the current MVP remains effectively single-symbol focused.

Required future work:
Validate multi-symbol positions, portfolio exposure and aggregate
risk.

Revisit:
After single-symbol execution is stable.

Priority:
MEDIUM