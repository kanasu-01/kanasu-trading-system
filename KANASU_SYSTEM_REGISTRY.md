# 📘 KANASU TRADING SYSTEM REGISTRY
(Single Source of Truth)

---

## Project Identity

- Project Name: Kanasu Trading System  
- Meaning: Kanasu (Kannada) = Dream  
- System Type: Professional, broker-agnostic, quant-grade trading system  
- Primary Market: NSE (India)  
- Current Status: Architecture & Foundation Phase (~10–15%)

---

## 1. Core Principles (LOCKED)

These principles must never be violated.

1. Broker-agnostic architecture  
2. Single responsibility per module  
3. Contract-first design  
4. Same strategy code for backtest, paper, and live  
5. Incremental evolution, no blind refactors  
6. Explainability over blind optimization  
7. Risk and safety before profitability  

---

## 2. Authoritative Project Structure

core/
├── broker/
│   ├── base_broker.py
│   ├── angelone.py
│   ├── csv_broker.py
│
├── market_data/
│   ├── base_feed.py
│   ├── historical_feed.py
│
├── execution/
│   ├── broker_execution_engine.py
│
├── backtest/
│   ├── backtest_engine.py
│   ├── bar_replay.py
│
├── strategies/
│   ├── base_strategy.py
│   ├── pivotboss_swing_strategy.py
│
├── metrics/
│   ├── volatility_metrics.py
│
├── models/
│   ├── accumulation_score.py
│   ├── distribution_score.py
│
├── risk/
│   ├── risk_manager.py
│   ├── stop_loss_manager.py
│   ├── drawdown_risk_manager.py
│
├── entities/
│   ├── candle.py
│   ├── candle_series.py

---

## 3. Core Contracts (CRITICAL)

### 3.1 BaseBroker Contract

All broker implementations must support:

- get_historical_candles(symbol, timeframe, start, end) -> List[Candle]
- place_order(order)
- cancel_order(order_id)
- get_order_status(order_id)
- get_account_balance()

Rules:
- Brokers return Candle entities only
- No raw API responses outside broker layer
- All broker quirks handled internally

---

### 3.2 HistoricalFeed Contract

- HistoricalFeed(broker)
- load(symbol, timeframe, start, end) -> List[Candle]

Rules:
- Orchestrates historical data
- Delegates fetching to broker
- Converts nothing, validates nothing
- Remains broker-agnostic

---

### 3.3 Strategy Contract

- on_new_candle(series) -> Optional[str]

Rules:
- Strategy must not know broker, feed, or execution
- Strategy is pure market logic
- No side effects

---

### 3.4 Backtest Engine Contract

- Event-driven
- Consumes List[Candle>
- Same strategy logic as live trading
- Deterministic and reproducible

---

## 4. Implemented Phases

- Phase 10.9B: HistoricalFeed introduced
- Phase 10.9C: Broker-aligned historical data access
- Phase 10.9D: CSVBroker added for offline and replay data

---

## 5. Explicitly Not Implemented Yet

- AngelOne real historical API wiring
- Data quality validation
- Timezone normalization
- Multi-symbol portfolio backtesting
- Performance analytics and reports
- Parameter optimization
- AI / ML models
- Live trading enablement

---

## 6. Change Management Rules

Before any change:

1. Identify affected module
2. Identify impacted contract
3. Identify project phase
4. Check core principle violation
5. Ensure reversibility

If unclear, pause and redesign.

---

## 7. Development Protocol

1. Review this registry
2. Design discussion
3. Explicit confirmation
4. Minimal change implementation
5. Commit with phase reference
6. Registry remains authoritative

---

## 8. Long-Term Vision

- Institutional accumulation and distribution detection