# Kanasu Paper Trading Module – Design Reference

## 1) Main idea

Paper Trading is a **long-running runtime module**.

It is different from Backtest.

* **Backtest** runs once, finishes, and returns a result.
* **Paper Trading** starts a session, keeps running, and must be monitored.

So Paper Trading needs:

* a **start** action
* a **stop** action
* a **status** view
* runtime state that stays alive while the session is running

---

## 2) Simple architecture

The flow should be:

**Frontend → FastAPI route → Paper Trading session/runtime → TradeExecutionEngine → PortfolioManager → response to frontend**

The frontend never talks directly to execution logic.
The frontend only talks to API endpoints.

---

## 3) What the frontend does

The frontend is only a **control and monitoring panel**.

It should:

* load strategy and symbol options from backend config
* let user select strategy and symbol
* send start request
* send stop request
* show current session status
* show active position
* show metrics
* show trade log

The frontend should **not** calculate trades, PnL, position size, or signals.

---

## 4) What the backend does

The backend owns the trading logic.

It should:

* receive start/stop/status requests
* create and manage the paper trading session
* run the strategy
* process candles
* execute trades through TradeExecutionEngine
* maintain portfolio and positions
* return current runtime snapshot to frontend

The backend should be the **single source of truth** for paper trading state.

---

## 5) How Paper Trading is different from Backtest

### Backtest

Backtest is a one-time job.

* user selects inputs
* backend runs the test
* backend returns a completed result
* frontend displays the result

### Paper Trading

Paper Trading is a live session.

* user starts a session
* backend keeps running
* frontend checks status
* user can stop the session
* frontend keeps monitoring live state

### Key difference

Backtest gives a **final result**.
Paper Trading gives a **current session state**.

---

## 6) How Paper Trading should be built

### Step 1: API contract first

Create endpoints like:

* `GET /api/paper-trading/config`
* `POST /api/paper-trading/start`
* `POST /api/paper-trading/stop`
* `GET /api/paper-trading/status`

This gives the frontend a stable contract.

### Step 2: Frontend page

Build the Paper Trading page with:

* configuration section
* session status card
* active position card
* metrics card
* trade log panel

### Step 3: Backend session logic

Create a Paper Trading session object that owns the running runtime.

This session should keep references to:

* strategy
* feed
* execution engine
* portfolio manager
* current status

### Step 4: Status snapshot

The status endpoint should return a snapshot of the current session.

It should include:

* session status
* selected strategy
* selected symbol
* active position
* metrics
* trade log

---

## 7) Why we avoid global state

Global state means a shared object that any file can change.

That is easy at first, but risky later.

Problems with global state:

* hard to track who changed it
* hard to debug
* can create duplication
* can break when future modules grow

So the better pattern is:

* keep state inside a session object
* expose only safe snapshots through API
* do not scatter state across many files

---

## 8) Why we avoid duplicate state

We already have state inside:

* `TradeExecutionEngine`
* `PortfolioManager`
* `PositionBook`

So we should not create another full copy of the same state in a separate object.

Instead:

* reuse existing runtime objects
* wrap them inside a session
* return snapshots from the session

This keeps one source of truth.

---

## 9) Recommended ownership model

### TradeExecutionEngine owns

* completed trades
* last execution event
* last execution price
* last execution quantity
* runtime position lookup

### PortfolioManager owns

* realized PnL
* unrealized PnL
* equity
* drawdown
* position book

### Paper Trading session owns

* session lifecycle
* start/stop control
* runtime references
* status snapshot

### Frontend owns

* buttons
* forms
* display cards
* polling or refresh calls

---

## 10) How this impacts future modules

This design will help future modules stay consistent.

### For Live Trading

Live Trading can reuse the same pattern:

* start session
* stop session
* status snapshot
* frontend dashboard

### For Broker Integration

Broker integration can be added behind the same session layer.

### For Multi-symbol support

A session-based design will make it easier to manage multiple symbols later.

### For Alerts and monitoring

Status snapshots can be reused for alerts, logs, notifications, and dashboards.

---

## 11) Kanasu rule for all future modules

Before adding a new object, ask:

* Is this a new source of truth?
* Does this duplicate existing runtime state?
* Should this belong to a session, engine, or snapshot?
* Can the frontend consume it through API instead?

If the answer creates duplication, simplify the design.

---

## 12) Short summary

Paper Trading in Kanasu should be built as:

* **Frontend** = control panel and live monitor
* **Backend route** = API gateway
* **Session** = runtime owner
* **Execution engine** = trade processor
* **Portfolio manager** = PnL and position tracker
* **Status snapshot** = data returned to frontend

This keeps the design clean, scalable, and reusable for future trading modules.
