# Kanasu Architecture Decisions

## Purpose and history

This ledger records architectural choices, their status and consequences. AD-001 through AD-007 are retrospective records of architecture established before this ledger was created. Their identifiers do not imply the ledger existed when the underlying implementation was completed.

Statuses:

- **ACCEPTED** — authoritative within its stated scope.
- **PROPOSED** — candidate requiring explicit acceptance before it becomes authoritative.
- **SUPERSEDED** — retained with a link to its replacement.

## Registry

### AD-001 — Authoritative simulated portfolio state

**Status:** ACCEPTED (retrospective)

PortfolioManager owns authoritative simulated cash, position value, equity, realized P&L, unrealized P&L and total P&L. PositionBook owns open Position objects. Consumers read snapshots instead of maintaining duplicate account state.

Established by M1. This does not claim live broker reconciliation.

### AD-002 — Execution-price and explicit-cost ownership

**Status:** ACCEPTED (retrospective)

SlippageModel owns simulated fill adjustment from a market reference price. BrokerageModel owns explicit transaction costs. TradeExecutionEngine applies each once and honors their independent configuration.

Established by M2. This does not establish exact broker/product charge fidelity.

### AD-003 — Candle value and sequence boundaries

**Status:** ACCEPTED (retrospective)

Candle validates finite OHLCV and its existing value relationships. CandleSeries validates whole-series duplicate, chronology and timezone-awareness consistency. Neither boundary silently sorts, repairs, localizes or converts timestamps.

Established by M3.1 and M3.4.

### AD-004 — Dataset identity and timezone metadata

**Status:** ACCEPTED (retrospective)

Dataset identity consists of symbol, optional timeframe and optional timezone. Timezone is identity metadata; it does not automatically localize, normalize, or convert Candle.timestamp.

Established by M3.3a and M3.3b.

### AD-005 — Canonical CSV loader

**Status:** ACCEPTED (retrospective)

core.market_data.csv_candle_loader is the canonical CSV implementation. The older core.data_loaders import remains a compatibility wrapper and must not regain independent parsing behavior.

Established by M3.2.

### AD-006 — Historical chunk composition

**Status:** ACCEPTED (retrospective)

Each broker response must be internally chronological and duplicate-free. Identical candles repeated from an earlier chunk may be skipped as overlap. A conflicting same-timestamp candle, a malformed chunk or a never-seen delayed candle is rejected.

Established by M3.5.

### AD-007 — Initial persistent historical store

**Status:** ACCEPTED (retrospective)

SQLite is the initial local historical candle store. Candle identity is dataset identity plus timestamp. Exact duplicate writes are idempotent; conflicts are rejected; batch writes are transactional.

Established by M3.6a. Coverage planning, provider orchestration and timestamp conversion are outside that decision.

<a id="ad-008--retrieval-coverage-and-expected-bar-completeness"></a>

### AD-008 — Retrieval coverage and expected-bar completeness

**Status:** ACCEPTED

The following are distinct:

~~~text
Stored candles
≠
Retrieval coverage
≠
Expected-bar completeness
≠
Source policy
~~~

M3.6b defines retrieval coverage and deterministic missing-range planning. It must not silently introduce market/holiday calendars, expected-bar generation, provider wiring, SQLite orchestration, timezone conversion, arbitrary naive/aware normalization, or source-policy implementation.

Retrieval coverage states what request interval has trustworthy retrieval evidence under a declared contract. Expected-bar completeness asks whether every market event or bar that should exist is represented; answering that later may require session, calendar, suspension, source and instrument semantics.

### AD-009 — Explicit historical source policy

**Status:** PROPOSED

Historical consumers select an explicit local-only, local-first or provider-backed policy. A request satisfiable from local storage should not require broker authentication.

Target step: M3.7.

### AD-010 — Real-data paper with simulated authority

**Status:** PROPOSED

V1 paper trading consumes real market data while using the validated simulated execution and PortfolioManager authority. The UI controls and observes the backend session; it does not own trading/account state.

Target milestones: M6 and M7.

### AD-011 — Instrument and account returns remain distinct

**Status:** PROPOSED

Instrument price return, gross/net trade outcome and account/equity return are different measures. Research and risk reporting choose the measure matching the question and must not use Trade.pnl_pct as a substitute for account return.

Target milestones: M4 and M5.

### AD-012 — API and UI use authoritative workflows

**Status:** PROPOSED

API and UI results come from actual research jobs and authoritative runtime snapshots. Placeholder responses are labelled as such and cannot be treated as evidence.

Target milestone: M8.

## Decision workflow

Create or update an AD when a choice changes module ownership, a durable contract, persistence identity/schema, accounting semantics, runtime boundaries, or a cross-cutting non-functional rule. Record context, alternatives, consequences, scope and evidence. Accepted decisions may be superseded but are never erased or renumbered.
