# Kanasu Paper Runtime

## Purpose

This document owns the accepted M7 paper-runtime design and its remaining V1 application boundaries. V1 paper trading may consume real AngelOne market data while simulating execution; it cannot place real-money broker orders.

## CURRENT STATE

Kanasu has two paper data-source modes:

- `MOCK` — deterministic CSV/`MockLiveFeed` operation for development and regression.
- `ANGELONE` — real market-data paper operation through the AngelOne live market-data session/feed.

Both use simulated `TradeExecutionEngine` execution and authoritative `PortfolioManager` accounting.

~~~text
AngelOne live market data
        ↓
AngelOneLiveCandleFeed
        ↓
LivePaperRuntime
        ↓
PaperCandleProcessor
        ↓
StrategyRunner
        ↓
simulated TradeExecutionEngine
        ↓
authoritative PortfolioManager
        ↓
PaperTradingSession snapshot + session journal
~~~

Real-money order routing is not part of this workflow.

## Ownership

| Component | Authority |
|---|---|
| AngelOne live market-data session/feed | Provider connectivity and accepted market observations/completed candles. |
| LivePaperRuntime | Provider thread, callback admission, session boundary, reconnect policy and failure propagation. |
| PaperCandleProcessor | Strategy/execution sequencing, pending intent and reconciliation state. |
| Strategy/StrategyRunner | Strategy state and completed-candle decisions. |
| TradeExecutionEngine | Simulated fills, protection and execution feedback. |
| PortfolioManager/PositionBook | Cash, position, equity and P&L authority. |
| PaperTradingSession | Runtime lifecycle, failure state and read-only authoritative snapshot. |
| TradeJournal | Per-session completed-trade evidence. |
| API/frontend | Not yet authoritative; M8 must connect them to this runtime. |

## Causal live execution

A decision made from completed candle N creates at most one pending intent.

The live path does not execute that intent from candle N, from wall-clock passage, or retrospectively from a later completed candle.

The intent may execute only when an accepted live source observation proves that the immediate N+1 interval has opened.

If the next observed interval skips N+1, the pending intent cannot be reinterpreted as executable at the later interval.

Every accepted live market update may protect an already-open position. The source observation that creates a new position is not reused retrospectively as a post-entry protective observation.

Completed live candles mark authoritative close state before strategy evaluation. Execution feedback is delivered before the next completed-candle decision.

## Provider supervision

`LivePaperRuntime` owns the provider thread and joins it on stop. Provider failures are surfaced rather than leaving a false healthy session.

Relevant configuration includes:

- `PAPER_DATA_SOURCE`
- `PAPER_SESSION_START`
- `PAPER_SESSION_END`
- `PAPER_CLOCK_INTERVAL_SEC`
- `BROKER_RETRY_ATTEMPTS`
- `BROKER_RETRY_DELAY_SEC`

Defaults for the retry settings are two attempts and two seconds delay.

At session end, callback admission closes before shutdown. A racing provider event cannot mutate paper state after the configured boundary, and no execution may be opened in a bar beginning at or after session end.

## Reconnect and reconciliation

A provider-data gap after strategy state exists cannot be treated as continuous live execution.

The accepted policy is:

1. invalidate the pending next-bar intent before reconnect;
2. preserve an already-open authoritative position;
3. quarantine the first observed reconnect interval;
4. use the next real interval transition to identify the completed historical gap;
5. recover that exact gap with canonical historical candles;
6. replay recovered candles into strategy state only; and
7. resume unrestricted live processing only after successful reconciliation.

Recovered historical OHLC cannot retrospectively create an entry, create a pending live intent, or mutate an already-open position.

Newly observed live prices remain authoritative for protection during restricted reconciliation.

Incomplete recovery is a runtime failure.

## Lifecycle and observability

Runtime-created paper sessions use human-readable unique IDs and propagate the same identity into the execution engine and session journal.

The accepted implementation lifecycle is:

~~~text
CREATED → RUNNING → STOPPED
                  ↘ FAILED
~~~

`FAILED` preserves failure type and message. `STOPPED` and `FAILED` are terminal.

The current implementation does not expose distinct public `STARTING` or `STOPPING` states. M8/M9 must either add them or explicitly validate/document the accepted public lifecycle.

`PaperTradingSession.snapshot()` reads authoritative execution and portfolio state. Its immutable snapshot includes:

- session identity and status;
- strategy and symbol;
- start/stop times;
- initial capital;
- cash, position value and equity;
- realized, unrealized and total P&L;
- peak equity and drawdown;
- active-position details;
- completed-trade count;
- most recent execution information; and
- failure type/message.

## Journaling

Each runtime-created session receives its own journal directory keyed by session ID. Completed trades are appended to CSV and JSONL with that identity.

Process-restart recovery of an interrupted session is not implemented.

## M8 application boundary

The accepted M7 runtime is not yet the application control plane.

Current `api/routes/paper_trading_routes.py` still creates singleton metadata-only session state and does not start or own `run_live_paper_trading()`.

The frontend therefore does not yet consume the authoritative M7 snapshot.

The backtest API likewise still returns a fixed mock result.

M8 must replace those placeholders with actual backend workflows and authoritative snapshots rather than duplicating trading/account state in the API or frontend.

## Remaining V1 boundaries

M7 is complete at its accepted scope, but V1 still requires:

- M8 authoritative research and paper API workflows;
- responsive frontend integration;
- explicit disposition of remaining operational-hardening items;
- final failure-scenario and observation evidence;
- final documentation synchronization; and
- M9 V1 acceptance/release validation.

See [Deferred Work](../roadmap/DEFERRED_WORK.md) and the [Validation Plan](../validation/VALIDATION_PLAN.md).

## Future live execution

V2 may reuse validated strategy, data, session-observability and account-domain concepts, but real-money execution additionally requires durable order/fill identity, idempotency, broker reconciliation, partial-fill/cancellation semantics, restart recovery and operational safety.
