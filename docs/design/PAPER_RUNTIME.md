# Kanasu Paper Runtime

## Purpose

This document owns the current and target V1 paper-runtime design. V1 paper trading consumes real market data and simulates orders; it does not place real-money broker orders.

## CURRENT STATE

Kanasu already has:

- strategy and StrategyRunner components;
- TradeExecutionEngine simulated fills and events;
- PortfolioManager authoritative simulated account state;
- position, trade, risk and journal-related components;
- a PaperRuntime composition;
- MockLiveFeed callback delivery; and
- API routes and frontend pages for paper-session controls/status.

The principal paper entry flow in main currently loads a CSV and replays it through MockLiveFeed. That is useful for deterministic runtime development, but it is not operational real-market-data paper trading.

The API paper start route creates a session metadata object. Start/stop/status operations update or expose session metadata; they do not start and own the complete feed, strategy, execution, portfolio and journal runtime. The API service currently uses process-level singleton state.

At the end of a synchronous mock feed, API-style session lifecycle and runtime completion are not unified. Current UI state therefore must not be treated as proof of a running simulated trading session.

## TARGET V1 STATE

~~~text
Real market data
        ↓
Paper runtime/session
        ↓
Strategy
        ↓
Risk and simulated execution
        ↓
Authoritative PortfolioManager state
        ↓
Journal and snapshot
        ↓
API
        ↓
Responsive frontend
~~~

The session owns the lifecycle and references needed for one running paper workflow. It does not duplicate execution or portfolio state.

### Ownership

| Component | Authority |
|---|---|
| Live market-data provider/feed | Provider connectivity, completed-candle delivery, freshness and connection state. |
| Paper session/runtime | Start/stop/failure lifecycle and references to the active runtime components. |
| Strategy/StrategyRunner | Strategy state and signals under the shared strategy contract. |
| TradeExecutionEngine | Simulated trade lifecycle, fill events and completed trades. |
| PortfolioManager/PositionBook | Cash, open positions, market value, equity and P&L. |
| Journal/result store | Durable append-oriented evidence and session identity. |
| API | Validated commands and authoritative snapshots. |
| Frontend | Controls, status and presentation only. |

The backend remains authoritative for trading and account state. The frontend must not reconstruct positions, equity or P&L from partial events.

### Session behavior

A target V1 session needs explicit states such as starting, running, stopping, stopped and failed. State must reflect actual feed/runtime activity. Start must initialize and own the runtime; stop must terminate delivery and release resources; feed exhaustion or failure must transition truthfully.

Snapshots should include session identity, status, dataset/source identity, selected strategy and effective configuration, feed freshness, current authoritative portfolio state, last execution information, completed trades or journal references, and current failure information.

### Live-data boundary

The live provider must emit canonical completed Candle objects under declared timestamp and ordering semantics. Duplicate, conflict, regression, staleness, disconnect and partial-candle behavior must be explicit. Real-data paper operation should be recordable for deterministic diagnosis and replay.

## KNOWN DIVERGENCES

- AngelOne live subscription is not implemented.
- Main paper mode uses CSV replay.
- API session creation is disconnected from PaperRuntime execution.
- Stop/status behavior manages metadata rather than a complete running runtime.
- Strategy-local position state lacks a complete execution feedback contract.
- Journal/session recovery and durable runtime identity are incomplete.
- Frontend paper data is not yet a full authoritative runtime snapshot.
- The dormant live broker-execution path is not compatible enough to serve as a V1 paper dependency.

These divergences are tracked in [Deferred Work](../roadmap/DEFERRED_WORK.md), especially DW-004. M6 and M7 are reserved roadmap milestones for real market-data ingestion and paper-session integration.

## V1 acceptance

The paper runtime is complete only when it satisfies the applicable requirements in the [Validation Plan](../validation/VALIDATION_PLAN.md#paper-runtime). This includes real market data, simulated execution, authoritative portfolio snapshots, truthful lifecycle states, failure handling, journals and an explicit guarantee that V1 cannot route a real-money order.

## Future live execution

V2 may reuse validated strategy, data, session-observability and account-domain concepts, but live execution additionally requires durable order/fill identity, idempotency, broker reconciliation, partial fills, restart recovery and operational safety. It is not enabled by swapping a simulated engine for a broker call.
