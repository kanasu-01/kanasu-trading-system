# Research and Paper Application

## 1. Status and purpose

**Milestone:** M8 — Research and Paper Application
**Status:** DESIGN BASELINE
**Starting repository baseline:** `390c7cc313fb782de9a82dc9e6b9c04be545f7b1`
**Accepted prior implementation baseline:** `7dd8e34dd6d9ce32eba7e67b3321738471253fd5`

M8 connects the already validated research and real-market-data paper engines to the FastAPI/React application without weakening their accepted behavior.

This document freezes the M8 application contracts, ownership boundaries, lifecycle/error behavior, supported V1 workflow and validation obligations. It does not claim that M8 production code has been implemented or validated.

## 2. Scope

M8 owns:

- application-level composition for authoritative Backtest execution;
- typed Backtest request/response contracts;
- application-level ownership of one active paper runtime;
- typed paper start/status/stop and snapshot contracts;
- thin FastAPI transport routes;
- authoritative backend-to-frontend state projection;
- API-base configuration suitable for the application environment;
- frontend Backtest and Paper workflows based on backend authority;
- application-boundary validation and DW-013 closure evidence.

M8 does not silently absorb:

- real-money broker order execution;
- V2 order identity, reconciliation, cancellation, partial-fill or recovery semantics;
- multi-symbol portfolio semantics;
- PivotBoss validation;
- process-restart recovery;
- broad broker authentication/session lifecycle redesign under DW-015;
- redesign of accepted M4/M5/M7 execution or accounting semantics;
- unrelated legacy replay/export repair;
- pixel-perfect frontend design before M8.4; or
- M9 final V1 release acceptance.

## 3. Starting application gaps

At the M8 starting baseline:

- `POST /api/backtest/run` returns a fixed mock result with `bt_mock_001`;
- `core/runtime/backtest_runtime.py::run_backtest()` returns `None` and mixes authoritative execution with CLI printing and optional replay/export/visualization side effects;
- paper API ownership creates `paper_mock_001` metadata rather than owning the M7 live paper runtime;
- current paper stop changes session metadata and clears it rather than stopping the real `LivePaperRuntime`;
- `run_live_paper_trading()`-style composition does not expose the authoritative session/runtime handle early enough for HTTP status and stop control;
- frontend/backend paper contracts have drifted;
- frontend API configuration contains a machine-specific URL;
- advertised `camarilla` configuration does not match the strategy factory; and
- PivotBoss remains outside the validated reference-strategy scope.

These are application-integration gaps. They are not evidence that M4, M5 or M7 trading semantics should be redesigned.

## 4. Authority and dependency rules

The authoritative ownership chain is:

~~~text
market data / historical source
        ↓
validated strategy + execution
        ↓
authoritative PortfolioManager
        ↓
BacktestResult or PaperTradingSession.snapshot()
        ↓
application projection
        ↓
FastAPI DTO
        ↓
React presentation
~~~

Rules:

1. FastAPI request/response models belong to the API/application boundary and do not become dependencies of trading/domain execution code.
2. React never becomes an accounting or trading-state authority.
3. The application may compose existing domain/runtime capabilities, but it must not duplicate their economic or causal logic.
4. Placeholder values may exist only when explicitly labelled as development/mock behavior and cannot be presented as validated output.
5. Domain/runtime exceptions are translated at the application/route boundary into stable API errors; domain code does not raise HTTP exceptions.
6. One application process initially owns at most one active paper session.
7. Process-restart recovery is unsupported in M8 unless separately designed and approved.

## 5. Supported V1 application choices

The initial authoritative M8 application exposes:

- reference strategy: `sma_crossover`;
- historical Backtest execution through the existing `HistoricalSource`;
- current single-symbol account semantics;
- real-market-data paper trading with simulated execution;
- the existing accepted public paper states `CREATED`, `RUNNING`, `STOPPED` and `FAILED`.

The application must not advertise `camarilla` while the strategy factory does not support it. PivotBoss may remain present in repository code but is not exposed as a validated M8 application strategy.

Historical source policy, broker credentials, retry behavior and other deployment/runtime settings remain backend configuration unless a separate application contract explicitly makes them user-selectable.

## 6. Backtest application contract

### 6.1 Request

`POST /api/backtest/run` accepts a typed request with these logical fields:

| Field | Contract |
|---|---|
| `symbol` | non-empty supported symbol identifier |
| `timeframe` | supported canonical timeframe identifier |
| `strategy_id` | initially `sma_crossover` |
| `start` | RFC 3339 / ISO timestamp accepted by the historical-source boundary |
| `end` | timestamp with `end > start` and compatible awareness |
| `timezone` | dataset timezone identity used for `DatasetContext`; metadata, not implicit timestamp conversion |
| `initial_capital` | finite, strictly positive number |
| `strategy_params` | typed/validated parameters for the selected strategy |

Replay, visualization and export flags are not part of the initial authoritative Backtest API request. The HTTP path does not trigger CLI-only presentation side effects.

For `sma_crossover`, application validation must reject invalid parameter combinations rather than passing arbitrary malformed values deeper into execution.

### 6.2 Composition

The application Backtest service composes:

~~~text
typed request
  → BacktestConfig/effective application configuration
  → DatasetContext
  → HistoricalSource
  → validated strategy
  → RuntimeContext
  → BacktestEngine.run_stream()
  → BacktestResult
  → PerformanceMetrics.summarize_backtest()
  → typed response
~~~

The route itself remains thin. Blocking Backtest execution runs outside the FastAPI event loop. The initial V1 API is request-scoped and synchronous: the HTTP request completes with the result or a truthful error. M8 does not introduce a research job queue unless later evidence proves it is necessary.

The application may refactor composition out of CLI-oriented `run_backtest()`, but it must not change M4/M5 execution economics to do so.

### 6.3 Response

A successful Backtest response contains:

- `run_id`: exactly `BacktestResult.session_id`;
- `status`: `completed`;
- the requested symbol/timeframe/strategy/time window needed to identify the result;
- `summary`: the authoritative result-aware metric projection;
- `equity_curve`: ordered `{timestamp, equity}` points from `BacktestResult.equity_curve`;
- `trades`: ordered completed-trade projections from `BacktestResult.trades`.

The authoritative summary keys are:

- `completed_trade_count`;
- `net_profitable_trade_count`;
- `net_losing_trade_count`;
- `net_breakeven_trade_count`;
- `net_profitable_trade_rate_pct`;
- `mean_positive_instrument_return_pct`;
- `mean_negative_instrument_return_pct`;
- `mean_instrument_return_pct`;
- `gross_realized_pnl`;
- `net_realized_pnl`;
- `mean_net_pnl_per_completed_trade`;
- `completed_trade_transaction_cost_total`;
- `account_pnl`;
- `account_return_pct`; and
- `max_equity_drawdown_pct`.

The API must not reintroduce ambiguous legacy Backtest names such as `expectancy_pct` or synthetic trade-compounded `max_drawdown_pct`.

Each trade projection preserves the existing authoritative `Trade` information required by the UI, including symbol, entry/exit timestamps and prices, stop, quantity, direction, exit reason, net/gross P&L, transaction cost and instrument return percentage.

M8 does not require the initial Backtest response to expose every `BarRecord` or repair the legacy Replay workflow. Replay/export expansion is separate unless explicitly added to M8.4.

### 6.4 Backtest failures

Stable application errors distinguish at least:

- malformed request / invalid field values;
- unsupported strategy/configuration;
- invalid historical request boundaries;
- unavailable provider/authentication when external history is required;
- historical retrieval/validation failure; and
- internal invariant/runtime failure.

Errors must not fabricate a run identifier or partial successful result.

## 7. Paper application control plane

### 7.1 Ownership object

The application introduces one process-local paper ownership object/handle containing enough authority to control and observe the real M7 runtime:

~~~text
PaperApplicationHandle
  ├─ PaperTradingSession
  ├─ LivePaperRuntime
  ├─ worker thread/task
  ├─ synchronization primitive/lock
  └─ retained terminal snapshot/reference
~~~

The exact class names may differ. The ownership obligations may not.

The authoritative `PaperTradingSession` and `LivePaperRuntime` must be constructed and registered with application ownership before the blocking worker starts. This is required so HTTP `/status` and `/stop` can act while the session is running.

### 7.2 Start

`POST /api/paper-trading/start` accepts a typed start request with:

- `symbol`;
- `strategy_id`, initially `sma_crossover`.

Initial capital, retry policy, provider credentials/session configuration and similar operational settings remain backend application configuration unless explicitly promoted into the public API later.

Start behavior:

1. acquire lifecycle synchronization;
2. reject a duplicate start while an active worker/session exists;
3. compose the authoritative M7 feed/session/strategy/execution/runtime graph;
4. register the application handle before worker execution;
5. start the worker;
6. return the authoritative current snapshot projection.

A duplicate start returns a stable conflict response and must not construct a second active provider/runtime.

### 7.3 Status

`GET /api/paper-trading/status` returns a typed wrapper:

~~~text
{
  active: boolean,
  snapshot: PaperTradingSnapshot | null
}
~~~

When a session exists, `snapshot` is an application serialization of the authoritative `PaperTradingSession.snapshot()` and contains:

- session ID;
- lifecycle status;
- strategy name;
- symbol;
- started/stopped timestamps;
- initial capital;
- cash;
- position size/value;
- equity;
- realized, unrealized and total P&L;
- peak equity;
- drawdown;
- active position;
- completed-trade count;
- latest execution event/price/quantity; and
- failure type/message.

`active` means the process currently owns a live worker/session requiring control. A retained terminal snapshot has `active=false` while still returning the terminal snapshot.

Before any session has existed, `active=false` and `snapshot=null`.

Snapshot acquisition must be consistent with concurrent paper-state mutation: either serialize snapshot reads through the applicable runtime/application synchronization boundary or publish an immutable snapshot atomically. The API must not assemble one response from independently observed mutable fields across an execution transition.

The frontend does not infer or repair missing snapshot values.

### 7.4 Stop

`POST /api/paper-trading/stop` controls the actual runtime.

Required behavior:

1. acquire/safely coordinate lifecycle ownership;
2. return a stable `409` lifecycle-conflict response when no active runtime exists;
3. call the real runtime stop surface;
4. wait for worker termination;
5. let the authoritative session become `STOPPED` unless a failure already made it `FAILED`;
6. preserve the terminal snapshot/reference;
7. return the terminal authoritative snapshot.

Clearing metadata without stopping the provider/runtime is invalid.

A timeout or runtime-stop failure is an application failure and must not be reported as a successful stop.

### 7.5 Worker completion and failure

Normal natural completion records `STOPPED`.

Uncaught provider/runtime failure records `FAILED` with the existing failure type/message contract. The application worker must propagate the failure into session state and terminal observability rather than losing it in the background thread.

Terminal session information is retained after worker completion. A later successful start may replace the previous terminal session as the current observable session.

M8 does not persist process-restart recovery state.

### 7.6 Paper lifecycle synchronization

At minimum, synchronization prevents:

- two concurrent successful starts;
- start racing with stop into two live runtimes;
- clearing/replacing a handle while its worker is still active;
- status observing a partially registered handle; and
- terminal completion overwriting a newer session.

The implementation should use the smallest locking/state mechanism that satisfies these invariants. M8 does not require a generalized multi-session manager.

## 8. API error contract

Application/API errors should have a stable machine-readable shape containing at least:

~~~text
{
  code: string,
  message: string
}
~~~

Optional structured details may be added where useful without exposing credentials or sensitive provider data.

Expected HTTP categories are:

- `422` for request-shape/value validation handled at the API boundary;
- `400` for supported-shape but unsupported application choices where appropriate;
- `409` for lifecycle conflicts such as duplicate paper start or stop-without-active-runtime;
- `5xx` for backend/provider/runtime failures that prevent the requested operation.

Exact exception classes remain implementation details. HTTP semantics remain outside the domain layer.

## 9. Frontend contract

The M8 baseline freezes behavior and authoritative data consumption, not final visual styling.

### Backtest screen

The Backtest workflow must expose:

- supported configuration choices from the backend/application contract;
- submit/loading state;
- request/validation failure state;
- truthful empty-result state;
- completed authoritative summary;
- authoritative equity curve;
- authoritative completed trades.

The screen does not compute account P&L, return or drawdown from trades.

### Paper screen

The Paper workflow must expose:

- supported start configuration;
- start in-progress/failure;
- authoritative running/stopped/failed lifecycle;
- current/terminal account state;
- active position when present;
- latest execution when present;
- runtime failure information;
- stop in-progress/failure.

While a paper session is active, the frontend may poll/refresh status at a bounded interval chosen in M8.4. Polling stops or backs off appropriately for terminal state. The frontend lifecycle label is always derived from the latest backend response, not a parallel local status model.

### Portfolio presentation

Any portfolio/equity/P&L/drawdown presentation shown during paper operation is a view of the paper snapshot. It is not an independently accumulated frontend portfolio.

### API configuration

The frontend API base URL comes from supported application/environment configuration. A developer machine-specific hard-coded URL is not an accepted M8 contract.

## 10. Detailed frontend design boundary

The baseline intentionally does not freeze:

- chart library choice;
- exact card/grid composition;
- typography and spacing;
- final responsive breakpoints;
- animation;
- detailed polling interval;
- final color semantics; or
- cosmetic interaction polish.

Those are M8.4 implementation decisions, provided they preserve the authority and lifecycle contracts in this document.

## 11. Milestone decomposition

### M8.1 — Application contracts and composition

Freeze this document, AD-012, supported strategy/config choices, DTO ownership, lifecycle/error behavior and application composition boundaries.

No production behavior is accepted merely by completing M8.1 documentation.

### M8.2 — Authoritative Backtest vertical slice

Implement and validate the real Backtest path from API request to authoritative typed response. Refactor composition as needed without changing M4/M5 economics.

### M8.3 — Authoritative Paper control plane

Implement application ownership of the real M7 paper runtime, including start/status/stop, synchronization, worker lifecycle, terminal snapshot retention and failure propagation.

Do not change M7 causal next-bar execution or reconciliation semantics.

### M8.4 — Frontend authoritative workflows

Replace placeholder/drifted frontend behavior with typed authoritative Backtest and Paper workflows, proper API configuration and responsive visible lifecycle/error states.

### M8.5 — Application integration validation and closure

Validate the complete application boundary, synchronize documentation and close/disposition DW-013 only with implementation evidence. M9 remains final V1 release acceptance.

## 12. Required validation evidence

M8 closure requires evidence for:

- typed Backtest request validation;
- supported-strategy/config validation;
- real historical Backtest execution;
- stable real `BacktestResult.session_id`;
- result-aware metrics;
- equity/trade response projection;
- Backtest empty/failure cases;
- paper real start;
- duplicate-start conflict;
- authoritative status;
- real runtime stop and worker termination;
- stop-without-active behavior;
- provider/runtime failure propagation;
- retained terminal snapshots;
- authoritative cash/position/equity/P&L/drawdown state;
- latest execution and active-position projection;
- frontend type/build/lint/focused interaction checks;
- loading/empty/running/stopped/failed UI states;
- responsive core workflow checks;
- no placeholder result being mistaken for validated output;
- no regression of accepted M4/M5/M7 semantics;
- documentation synchronization; and
- DW-013 disposition.

## 13. Deferred boundaries

DW-013 remains open until M8 implementation evidence removes the fixed Backtest result and paper-runtime disconnection.

DW-015 remains a separate broker session/authentication lifecycle hardening item. M8 may consume the current broker composition necessary for its accepted workflow, but it must not silently redesign session persistence, refresh, token storage or cross-restart reuse.

Real-money execution remains V2 work.

## 14. Acceptance statement

This design baseline is accepted when the M8 documentation diff is reviewed and approved. Acceptance authorizes only the documented M8 implementation sequence under the repository's normal inspect → design → modify → test/diff-check → stage → staged-diff review → commit → push gates.

Design acceptance is not implementation acceptance, test evidence, staging approval, commit approval or push approval.
