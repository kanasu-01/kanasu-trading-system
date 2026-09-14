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

M3.6b coverage intervals are half-open: `[start, end)`. The start is included and the end is excluded. Overlapping and touching coverage is continuous for planning, so subtraction requires no datetime epsilon or timeframe assumption.

This is the coverage planner's interval contract. It does not change SQLiteCandleStore.load(), whose candle-read range remains inclusive at both ends. Translating between those contracts belongs to M3.6c.

Retrieval coverage states what request interval has trustworthy retrieval evidence under a declared contract. Expected-bar completeness asks whether every market event or bar that should exist is represented; answering that later may require session, calendar, suspension, source and instrument semantics.

### AD-009 — Explicit historical source policy

**Status:** ACCEPTED

**Target:** M3.7

Historical source composition owns an explicit policy above local persistence and external-provider capabilities:

- `LOCAL_ONLY` uses persisted local retrieval evidence only. It never constructs or contacts an external provider and never requires broker authentication. Complete local coverage returns local candles; incomplete coverage fails explicitly with the remaining missing ranges and cannot fall back to a provider.
- `LOCAL_FIRST` checks trusted local coverage first. Complete local coverage returns without invoking a provider factory, constructing a broker or logging in. When coverage is incomplete, provider construction is lazy and occurs only after the missing ranges are known; only those ranges are fetched through the accepted M3.6 contracts.
- `PROVIDER_BACKED` requires external provider access for the requested interval. Pre-existing local coverage cannot suppress that access or independently declare the provider-sourced request complete, though local state remains available for persistence and conflict handling.

Source policy is not a `BaseBroker` or `AngelOneBroker` responsibility. `RuntimeMode` answers which operation Kanasu runs; historical source policy answers where historical data may or must come from. The two concepts remain independent. Backtest and WFA should consume canonical historical candles without owning the local/provider choice.

The broker historical provider adapter must reuse `HistoricalFeed`, which continues to own broker request limits, chunk traversal, overlap reconciliation, duplicate/conflict rejection and chronological chunk validation. A successfully completed external request supplies explicit coverage for its requested interval, including a confirmed-empty result with no candles. Coverage is never inferred from candle count, first/last timestamps, spacing or an expected number of bars. Provider failures and malformed results create no coverage claim; market calendars, holiday/session inference and expected-bar completeness remain outside this decision.

M3.7 preserves M3.6 timestamp fidelity and comparison rules. It does not normalize to UTC, localize timestamps, strip offsets or silently convert naive/aware values. Request/provider awareness compatibility must be explicit. Current `BacktestConfig` boundaries can be naive while provider timestamps can be aware, so this is a required design and validation concern.

Current AngelOne historical retrieval rejects an empty candle result. M3.7b must determine and test the minimal adapter or broker correction needed to support confirmed-empty external evidence; this acceptance does not claim that concern is fixed.

Accepted during M3.7 baselining. External provider construction is lazy.

M3.7a implementation evidence: `073f3e9 Add historical source policy contract`.

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

### AD-013 — Local historical retrieval evidence and timestamp comparison

**Status:** ACCEPTED

**Target:** M3.6c

Local historical retrieval uses explicit coverage supplied by the provider result. Candle presence, candle count, spacing, and first or last timestamps do not imply retrieval coverage. A result with full coverage is successful whether it contains candles or confirms an empty interval; subset coverage is partial; a result without coverage evidence is unknown and rejected; and a provider failure creates no coverage claim.

Persisted ISO timestamps are parsed back to Python `datetime` values for chronological ordering and range filtering. Within one `DatasetContext`, persisted candle and retrieval-coverage timestamps use one timezone-awareness style; differing aware offsets remain valid and use normal Python comparison semantics. Aware timestamps representing the same absolute instant are one candle identity even when their serialized offsets differ; the existing stored representation is retained. The store does not localize, normalize, strip offsets, or otherwise convert timestamp identity. Dataset timezone remains metadata.

Candles and coverage from one accepted provider result are persisted in one SQLite transaction. If candle persistence conflicts or fails, its coverage is rolled back with it. Historical source-policy selection and provider construction remain outside M3.6c and are targeted by M3.7.

## Decision workflow

Create or update an AD when a choice changes module ownership, a durable contract, persistence identity/schema, accounting semantics, runtime boundaries, or a cross-cutting non-functional rule. Record context, alternatives, consequences, scope and evidence. Accepted decisions may be superseded but are never erased or renumbered.
