# Kanasu System Architecture

## 1. Purpose

This document owns Kanasu's current and target system architecture. It describes implemented boundaries separately from intended behavior and known divergences. Product scope belongs in the [Product Vision](../PRODUCT_VISION.md), current delivery status in [Project Status](../PROJECT_STATUS.md), and implementation order in the [Roadmap](../roadmap/ROADMAP.md).

## 2. Architecture principles

- Keep strategy, market data, execution, portfolio, risk, reporting, UI, and broker responsibilities explicit.
- Keep one authoritative owner for simulated cash, positions, equity, and P&L.
- Convert source-specific market data to canonical Candle objects at a defined boundary.
- Reuse validated core behavior across runtimes without duplicating runtime state.
- Prefer small capability boundaries and incremental migration over a universal framework.
- Make current implementation, target design, validation, and release readiness distinct.

## 3. Current architecture

### CURRENT

| Area | Current responsibility |
|---|---|
| core/entities | Candle, CandleSeries, signals, positions, trades and other domain entities. |
| core/market_data | Feed abstractions, historical chunk retrieval/composition, mock live replay, canonical CSV parsing, and SQLite candle persistence. |
| core/data_loaders | Compatibility import path delegating CSV parsing to core/market_data. |
| core/broker | Broad broker abstraction plus current AngelOne and legacy CSV implementations. |
| core/strategies | Strategy contracts, strategy runner, and strategy implementations. |
| core/execution | Simulated trade execution/economics and a separate dormant broker-execution path. |
| core/portfolio | Authoritative simulated account state and open-position ownership. |
| core/risk | Position sizing, stops and recorded drawdown controls. |
| core/backtest | Historical strategy/execution loop, bar reporting, results and replay-related paths. |
| core/walk_forward | Window generation, optimization, out-of-sample evaluation and aggregation. |
| core/runtime | Backtest, walk-forward and paper runtime orchestration plus dataset identity. |
| api | Backtest configuration/mock result and paper-session metadata endpoints. |
| frontend | Browser pages for home, backtest, replay, paper and portfolio workflows. |

The repository is effectively single-symbol. Some containers could hold multiple positions, but aggregate capital, exposure and risk semantics have not been validated as a multi-symbol portfolio.

## 4. Current data flow

### CURRENT

~~~text
Backtest:
configuration → broker login → HistoricalFeed → BacktestEngine
    → StrategyRunner/CandleSeries → TradeExecutionEngine
    → PortfolioManager snapshot → BarRecord/BacktestResult

Walk-forward:
BacktestConfig → historical broker retrieval → WalkForwardRunner
    → GridSearchOptimizer/BacktestEngine → out-of-sample BacktestEngine
    → aggregate result

Principal paper entry flow:
CSV → canonical CSV loader → MockLiveFeed
    → PaperRuntime → StrategyRunner → TradeExecutionEngine
    → authoritative PortfolioManager

API/frontend:
browser → API routes
    → fixed mock backtest response OR paper session metadata
~~~

SQLiteCandleStore is implemented but is not yet used by backtest, WFA, or paper orchestration.

## 5. Simulated execution and accounting

### CURRENT

TradeExecutionEngine owns simulated trade lifecycle and execution events. It applies slippage once to the market reference price and uses BrokerageModel for explicit transaction costs when enabled.

PortfolioManager owns authoritative simulated cash, position value, equity, realized P&L, unrealized P&L, total P&L, and portfolio snapshots. PositionBook owns open Position objects. Backtest bar reporting reads the execution engine's portfolio snapshot rather than maintaining a second reporting portfolio.

Established invariants include:

~~~text
equity = cash + market value of open positions
total_pnl = equity - initial_capital
total_pnl = realized_pnl + unrealized_pnl
~~~

A BUY decided at a completed candle's close cannot be stopped by that candle's earlier low. A subsequent candle can trigger the stop.

### KNOWN DIVERGENCES

- Strategy-local position state does not receive a complete execution-acceptance/rejection/forced-exit feedback contract.
- Stop processing marks the current close before testing the stop, and gap-through-stop fill semantics remain simplified.
- Risk sizing uses fixed initial capital and does not establish affordability or dynamic-equity sizing.
- Brokerage is a simplified research cost model, not a declaration of exact broker/product tax fidelity.
- Broader equity-based daily/weekly drawdown semantics remain deferred.

## 6. Historical-data architecture

### CURRENT

Candle is a frozen domain entity. It rejects non-finite OHLCV, invalid high/low relationships, and negative volume. It does not convert timestamps or require positive prices, strictly positive volume, integer volume, or timezone awareness.

CandleSeries owns and validates its sequence. It rejects duplicates from anywhere in the series, never-seen delayed timestamps, and mixed naive/aware timestamps. It does not sort, deduplicate, localize, convert, fill gaps, or enforce timeframe spacing.

HistoricalFeed.stream() validates each returned broker chunk, rejects same-chunk duplicates/backward ordering/timezone-style mismatches, skips identical cross-chunk overlap, rejects conflicting overlap, and rejects never-seen delayed candles. Its timestamp index supports average O(1) lookup. Shared request boundaries remain intentional. HistoricalFeed.load() directly delegates and does not provide the same composition contract.

core.market_data.csv_candle_loader is the canonical CSV parser. core.data_loaders.csv_candle_loader is a compatibility wrapper.

SQLiteCandleStore persists candles by deterministic dataset identity plus ISO timestamp. It provides inclusive range reads, chronological database query ordering, exact-duplicate idempotence, conflict rejection, atomic batch save, and persistence across instances.

Dataset identity currently contains:

~~~text
symbol
timeframe (optional)
timezone (optional metadata)
~~~

Timezone identity does not imply timestamp localization or conversion.

### KNOWN DIVERGENCES

- The persistent store has no coverage or retrieval orchestration yet.
- ISO timestamp text filtering/order is not a general cross-offset chronology and can conflict with incompatible naive/aware request bounds.
- Provider empty/partial response and completeness semantics are not established.
- Historical CSV export and legacy CSVBroker/replay paths retain stale contracts.
- Main currently authenticates a broker before mode selection, so a conceptually local run is not fully local.

## 7. Research architecture

### CURRENT

BacktestEngine processes candles through the strategy and authoritative simulated portfolio, records bar state, and returns trades, bars and an equity curve. Walk-forward modules provide parameter search, in-sample/out-of-sample evaluation and aggregate results.

### KNOWN DIVERGENCES

- Expanding-window generation can fail to terminate.
- WFA creates backtests with hardcoded capital/fresh runtime settings instead of preserving all effective economics.
- Some performance calculations use instrument Trade.pnl_pct or a synthetic compounded trade-return curve where account equity is required.
- Research results do not yet carry a complete reproducibility manifest or dataset fingerprint.
- The PivotBoss implementation has unvalidated state/signal-contract issues and must not be treated as a validated research strategy.

## 8. Paper-runtime architecture

### CURRENT

The simulated execution, portfolio and paper-runtime building blocks exist. The principal paper entry path replays CSV candles through MockLiveFeed. API paper endpoints create and mutate session metadata but do not start or own the complete feed/strategy/execution runtime.

See [Paper Runtime](../design/PAPER_RUNTIME.md) for the current/target lifecycle.

## 9. API and frontend architecture

### CURRENT

The API exposes backtest and paper routes. The backtest run route returns a fixed mock result. Paper routes expose a singleton-backed session metadata lifecycle. The React/TypeScript/Vite frontend provides Home, Backtest, Replay, Paper and Portfolio pages and calls these APIs. The frontend is not yet a complete validated research or paper control plane.

The backend remains the intended authority for trading and account state. The frontend presents commands, status and snapshots.

## 10. Known divergences

Authoritative details are tracked in [Deferred Work](../roadmap/DEFERRED_WORK.md). The most material V1 divergences are:

- local storage is not integrated into a local-first historical service;
- retrieval coverage is not represented;
- backtest and WFA validity work remains;
- real live-market-data paper ingestion is absent;
- paper API sessions and the actual runtime are disconnected;
- the backtest API is a placeholder;
- live subscription and real-money execution are outside V1; and
- legacy replay/export/broker paths do not match current entities and constructors.

## 11. Target architecture

### TARGET

~~~text
CSV / broker historical API / local SQLite / live provider
                         ↓
       source parsing + normalization boundary
                         ↓
          canonical validated Candle stream
                         ↓
        one downstream strategy/execution core
             ↙             ↓             ↘
        Backtest          WFA      real-data Paper
             ↘             ↓             ↙
           authoritative simulated PortfolioManager
                         ↓
              journals/results/snapshots
                         ↓
                    real API
                         ↓
                responsive frontend
~~~

Historical retrieval should be a small service that combines explicit source policy, trusted retrieval coverage, the local store, provider access, and the existing validation boundaries. A fully local request should not require broker authentication. The service must distinguish stored candles, retrieval coverage, expected-bar completeness, and source policy.

Live paper uses real market data but simulated execution and authoritative simulated accounting. Real broker execution belongs to V2 behind order identity, reconciliation, recovery and operational safety contracts.

## 12. Architecture decisions

The decision register is [DECISIONS.md](DECISIONS.md). AD-001 through AD-007 retrospectively document architecture already established by M1–M3.6a. Later decisions retain their recorded status until explicitly accepted or superseded.
