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
| core/market_data | Feed abstractions, historical chunk retrieval/composition, a broker-backed HistoricalProvider adapter, mock live replay, canonical CSV parsing, SQLite candle/coverage persistence, deterministic missing-range planning, validated local-first retrieval, and the isolated historical source-policy boundary. |
| core/data_loaders | Compatibility import path delegating CSV parsing to core/market_data. |
| core/broker | Broad broker abstraction plus current AngelOne and legacy CSV implementations. |
| core/strategies | Strategy contracts, strategy runner, and strategy implementations. |
| core/execution | Simulated trade execution/economics and a separate dormant broker-execution path. |
| core/portfolio | Authoritative simulated account state and open-position ownership. |
| core/risk | Position sizing, stops and recorded drawdown controls. |
| core/backtest | Historical strategy/execution loop, bar reporting, results and replay-related paths. |
| core/research | Existing placeholder `ResearchSession`, `ResearchRequest` and `ResearchResult` workflow plus implemented deterministic canonical serialization, versioned dataset/configuration/result fingerprints, immutable research-evidence records, and dedicated SQLite evidence persistence. |
| core/walk_forward | Window generation, optimization, out-of-sample evaluation and aggregation. |
| core/runtime | Backtest, walk-forward and paper runtime orchestration plus dataset identity. |
| api | Backtest configuration/mock result and paper-session metadata endpoints. |
| frontend | Browser pages for home, backtest, replay, paper and portfolio workflows. |

The repository is effectively single-symbol. Some containers could hold multiple positions, but aggregate capital, exposure and risk semantics have not been validated as a multi-symbol portfolio.

## 4. Current data flow

### CURRENT

~~~text
Backtest:
configuration → HistoricalSource → canonical historical candles → BacktestEngine
    → StrategyRunner/CandleSeries → TradeExecutionEngine
    → PortfolioManager snapshot → BarRecord/BacktestResult

Walk-forward:
BacktestConfig → HistoricalSource → canonical historical candles → WalkForwardRunner
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

SQLite persistence, explicit retrieval coverage, missing-range planning and LocalFirstHistoricalService are implemented and validated together. HistoricalSourcePolicy and HistoricalSource implement the `LOCAL_ONLY`, `LOCAL_FIRST` and `PROVIDER_BACKED` selection contract. HistoricalFeedProvider implements the broker-backed HistoricalProvider capability by composing HistoricalFeed. AppConfig now owns the source-policy, database-path and request-delay configuration, and main composes HistoricalSource after selecting BACKTEST or WALK_FORWARD. Both research runtimes retrieve canonical candles through this boundary instead of depending directly on BaseBroker or HistoricalFeed.

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

SQLiteCandleStore persists candles and explicit retrieval coverage by deterministic dataset identity. It provides inclusive candle reads using parsed Python datetime comparison, exact-duplicate idempotence, conflict rejection, transactional candle-plus-coverage writes, and persistence across instances. It preserves timestamp representation, rejects mixed naive/aware dataset state, and permits differing aware offsets under Python datetime semantics.

The M3.6 coverage planner deterministically subtracts persisted half-open coverage from a requested `[start, end)` interval. LocalFirstHistoricalService uses that planner, fetches only missing ranges from an injected provider, validates explicit provider evidence and canonical candle sequence, persists accepted results transactionally, and reloads a chronological half-open result. Confirmed-empty and partial coverage are explicit; candle presence never implies retrieval coverage. Durable cold-to-warm reuse and failure behavior are validated.

HistoricalSource owns source-policy selection and accepts a lazy provider factory. `LOCAL_ONLY` and warm `LOCAL_FIRST` retrieval avoid provider construction; missing `LOCAL_FIRST` coverage creates one provider and delegates to LocalFirstHistoricalService; `PROVIDER_BACKED` contacts the provider for the complete request and determines completion from that result's explicit coverage alone. Provider-result validation and half-open local loading are shared with the M3.6 service. Provider-backed persistence is currently non-destructive; refresh and replacement semantics are not established.

HistoricalFeedProvider is the implemented bridge from the HistoricalProvider contract to HistoricalFeed. It collects the canonical completed stream, excludes only an exact request-end candle for half-open provider semantics, validates the resulting provider evidence through the shared M3.6 boundary, and claims full request coverage only after successful stream completion. Sparse and confirmed-empty results remain valid retrieval evidence. HistoricalFeed continues to own broker limits, chunk traversal, overlap reconciliation, duplicate/conflict rejection, chronology and stream-awareness validation. AngelOne accepts a valid empty historical data collection while malformed responses remain errors.

The historical-source composition factory creates SQLiteCandleStore and HistoricalSource immediately and ensures the database parent directory exists. It does not load AngelOne credentials, construct AngelOneBroker or log in. Its lazy provider closure calls the source-policy-unaware broker factory with `paper_mode=True` and `enable_historical_api=True`, then constructs HistoricalFeed with the configured request delay and wraps it in HistoricalFeedProvider. Complete `LOCAL_ONLY` and warm `LOCAL_FIRST` retrieval therefore require no external construction; missing `LOCAL_FIRST` and `PROVIDER_BACKED` invoke the external path according to HistoricalSource policy.

Backtest and WFA accept HistoricalSource, form a DatasetContext and half-open TimeRange from the configured request, and consume the returned canonical candles. They do not import BaseBroker or HistoricalFeed and contain no source-policy branching. Main performs no unconditional broker construction before runtime selection and composes this source only for BACKTEST and WALK_FORWARD; PAPER and LIVE received no historical-source behavior in M3.7c.

The default AngelOne-oriented BacktestConfig uses explicit Asia/Kolkata-aware request boundaries. This is configuration, not automatic localization: DatasetContext timezone remains metadata, timestamps pass through unchanged, and incompatible request/provider awareness remains an explicit validation failure.

Dataset identity currently contains:

~~~text
symbol
timeframe (optional)
timezone (optional metadata)
~~~

Timezone identity does not imply timestamp localization or conversion.

### KNOWN DIVERGENCES

- M3.7d completed the source-policy integration/failure matrix and resolved DW-011 at the accepted M3.7 scope.
- User-supplied request boundaries can still be naive while external provider timestamps can be aware; the accepted adapter/runtime boundary rejects incompatibility without silent normalization.
- Historical CSV export and legacy CSVBroker/replay paths retain stale contracts.

## 7. Research architecture

### CURRENT

BacktestEngine processes candles through the strategy and authoritative simulated portfolio, records bar state, and returns trades, bars and an equity curve. Walk-forward modules provide parameter search, in-sample/out-of-sample evaluation and aggregate results. `core/research` retains the minimal placeholder `ResearchSession`/`ResearchRequest`/`ResearchResult` workflow and now also implements the standalone M3.8c reproducibility primitives: deterministic canonical serialization, versioned dataset/configuration/stable-result fingerprints, immutable research-evidence records, and dedicated SQLite evidence persistence.

M3.8a, M3.8b and M3.8c are complete and validated at their accepted scopes. Historical SQLite continues to own only historical candles and retrieval coverage. Research evidence uses a physically separate SQLite store, and provenance remains separate from canonical dataset identity.

The M3.8c primitives are not automatically wired into `run_backtest()`, HistoricalSource, main, WFA, API or frontend. The complete provider-fresh → Backtest → fingerprints → evidence persistence → durable-local rerun integration remains unimplemented and unvalidated M3.8d work.

### TARGET

~~~text
canonical ordered candles + DatasetContext + requested TimeRange
                              ↓
                    dataset fingerprint

effective Backtest research configuration
                              ↓
                 configuration fingerprint

stable BacktestResult content (excluding session_id)
                              ↓
                     result fingerprint

three fingerprints + provenance + evidence metadata
                              ↓
             immutable research evidence record
                              ↓
              separate research-evidence SQLite store
~~~

The M3.8c implementation owns versioned canonical serialization and the three deterministic identity domains, a minimal evidence model, and dedicated evidence persistence. Historical SQLite continues to own only historical candles and retrieval coverage. Research evidence is stored separately, and provenance remains inspectable without becoming part of canonical dataset identity. These capabilities remain intentionally outside Backtest, HistoricalSource, main, WFA, API and frontend composition; the complete fresh/local repeated-run flow belongs to M3.8d.

### KNOWN DIVERGENCES

- Expanding-window generation can fail to terminate.
- WFA creates backtests with hardcoded capital/fresh runtime settings instead of preserving all effective economics.
- Some performance calculations use instrument Trade.pnl_pct or a synthetic compounded trade-return curve where account equity is required.
- Research runtimes do not yet compose the implemented fingerprints and evidence store into a complete persisted reproducibility record.
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

- M3.8a historical-input parity, M3.8b stable Backtest-result parity and M3.8c identity/evidence persistence are validated at their accepted scopes, while M3.8d full repeated-run integration remains unimplemented and unvalidated;
- backtest and WFA validity work remains;
- real live-market-data paper ingestion is absent;
- paper API sessions and the actual runtime are disconnected;
- the backtest API is a placeholder;
- live subscription and real-money execution are outside V1; and
- legacy replay/export/broker paths do not match current entities and constructors.

## 11. Target architecture

### TARGET

~~~text
Backtest / WFA historical request
                         ↓
      explicit historical-source composition
       ├─ LOCAL_ONLY → local store/coverage only
       ├─ LOCAL_FIRST → local store/coverage → missing ranges only
       │                                      ↓
       │                              lazy HistoricalProvider
       └─ PROVIDER_BACKED → required HistoricalProvider
                                              ↓
             HistoricalFeedProvider → HistoricalFeed → BaseBroker
                         ↓
           accepted candles and explicit coverage
                         ↓
             local persistence and validation
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

Historical source composition combines explicit policy, trusted retrieval coverage, the local store, lazy provider access, and existing validation boundaries. `LOCAL_ONLY` and fully covered `LOCAL_FIRST` requests do not construct a provider or authenticate a broker; `PROVIDER_BACKED` requires external access. Source policy remains separate from `RuntimeMode` and from broker capability. HistoricalFeed retains broker chunk composition/validation beneath the provider adapter. The composition layer continues to distinguish stored candles, retrieval coverage, expected-bar completeness, and source policy.

The implemented M3.7c runtime composition gives `AppConfig` ownership of historical source policy, local database path and request delay. The accepted V1 defaults are `LOCAL_FIRST`, `data/historical.sqlite3` and `0.5`. The historical-source factory constructs SQLiteCandleStore and HistoricalSource immediately but supplies an external-provider closure without invoking it. Only that closure loads AngelOne configuration, calls the existing eager broker factory with `paper_mode=True` and `enable_historical_api=True`, constructs HistoricalFeed and wraps it in HistoricalFeedProvider.

Main now selects BACKTEST or WALK_FORWARD before composing the historical source and performs no unconditional broker construction or login. Both research runtimes accept HistoricalSource, form the request from BacktestConfig boundaries, and retrieve canonical candles with DatasetContext and a half-open TimeRange. They do not import BaseBroker or HistoricalFeed and do not branch on source policy. PAPER and LIVE composition remains unchanged by M3.7c.

The default AngelOne-oriented BacktestConfig carries explicit timezone-aware Asia/Kolkata start/end values. This is an explicit example configuration choice. DatasetContext timezone remains metadata and does not localize arbitrary inputs; compatible naive local datasets remain supported, while incompatible request/provider awareness fails through existing validation.

Live paper uses real market data but simulated execution and authoritative simulated accounting. Real broker execution belongs to V2 behind order identity, reconciliation, recovery and operational safety contracts.

## 12. Architecture decisions

The decision register is [DECISIONS.md](DECISIONS.md). AD-001 through AD-007 retrospectively document architecture already established by M1–M3.6a. Later decisions retain their recorded status until explicitly accepted or superseded.
