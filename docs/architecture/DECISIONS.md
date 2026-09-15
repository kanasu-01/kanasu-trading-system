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

M3.7b established that a valid successful AngelOne response with an empty data collection returns an empty candle list, while malformed responses remain errors. This supports confirmed-empty external evidence without inferring coverage from candle presence.

Accepted during M3.7 baselining. External provider construction is lazy.

M3.7a implementation evidence: `073f3e9 Add historical source policy contract`.

### AD-010 — Real-data paper with simulated authority

**Status:** PROPOSED

V1 paper trading consumes real market data while using the validated simulated execution and PortfolioManager authority. The UI controls and observes the backend session; it does not own trading/account state.

Target milestones: M6 and M7.

### AD-011 — Instrument and account returns remain distinct

**Status:** ACCEPTED

Instrument price return, gross/net trade outcome and account/equity return are different measures. Research and risk reporting choose the measure matching the question and must not use Trade.pnl_pct as a substitute for account return.

Target milestones: M4 and M5.

Accepted during M4 baselining. This acceptance defines the durable reporting distinction; it does not claim that M4 or M5 implementation is complete.

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

### AD-014 — Research reproducibility evidence is separate from historical market-data persistence

**Status:** ACCEPTED

**Target:** M3.8

Historical candle and retrieval-coverage persistence remains the responsibility of the historical store. Research run identity, deterministic fingerprints, reproducibility evidence and references to detailed result artifacts belong to a separate research-evidence persistence boundary. Backtest or WFA research-result tables must not be added to the historical candle database.

The initial research-evidence implementation may use a separate SQLite database/file, but it must remain logically and physically separate from the historical store. Source and provider provenance is recorded separately from canonical dataset identity so equivalent provider-fresh and local-store data can produce the same dataset fingerprint while retaining inspectable provenance.

Dataset, research-configuration and stable-result fingerprint contracts use explicit versioned canonical serialization. Random execution-instance identifiers such as `session_id` and presentation-only options do not define research-result identity. Any other excluded nondeterministic field requires explicit justification.

This decision does not prescribe a detailed SQL schema or final database filename. A minimal evidence record may contain fingerprints, run/request identity, provenance, repository revision, summary data and references to detailed artifacts. A complete research catalog, analytics/reporting warehouse and UI remain outside this decision.

### AD-015 — Canonical research identity and evidence-record v1

**Status:** ACCEPTED

**Target:** M3.8c

AD-015 refines AD-014; it does not supersede it. AD-014 owns the separation between historical market-data persistence and research-evidence persistence. AD-015 freezes the v1 canonical identity and logical evidence-record contracts within that separate boundary.

#### Three fingerprint domains

M3.8c defines independent dataset, research-configuration and stable-result fingerprints. Each domain carries an explicit versioned schema identifier conceptually equivalent to `kanasu.dataset.v1`, `kanasu.backtest-config.v1` and `kanasu.backtest-result.v1`, persisted inside its canonical payload. Fingerprint output uses SHA-256 in self-describing form: `sha256:<64 lowercase hexadecimal characters>`.

The implementation must not use Python `hash()`, `repr()`, object identity, memory addresses, arbitrary `str(object)` fallback or insertion-order-dependent mappings as authoritative identity.

#### Canonical serialization v1

Canonical values are explicitly type-tagged so meaningful distinctions survive: `1` differs from `1.0`; list differs from tuple; and `None`, `"None"` and `False` remain distinct. V1 supports only:

- `None`, tagged as a null/none value;
- `bool`, tagged as Boolean;
- `int`, tagged with its decimal integer representation;
- finite `float`, tagged with its exact `float.hex()` representation;
- `str`, tagged as a Unicode string;
- `datetime`, tagged with `datetime.isoformat(timespec="microseconds")`;
- ordered `list` and `tuple`, with distinct tags and recursively canonicalized values; and
- mappings with string keys sorted lexicographically and recursively supported values.

Unsupported values and non-finite floats fail explicitly and are never stringified. Datetime serialization preserves the supplied representation and UTC offset; it does not normalize to UTC, localize naive values, strip offsets or convert awareness.

The tagged representation is encoded as deterministic UTF-8 JSON using semantics equivalent to `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False` and `allow_nan=False`. SHA-256 hashes those exact bytes.

#### Dataset fingerprint v1

Dataset identity contains the `DatasetContext` symbol, timeframe and timezone metadata; requested half-open `TimeRange` start and end; and canonical ordered candles with timestamp and complete OHLCV values. The candle sequence must already satisfy the canonical chronological boundary. Fingerprinting does not sort, deduplicate, repair chronology or normalize timestamps; invalid/noncanonical input fails explicitly.

Source policy and provider provenance are excluded from dataset identity and are recorded separately. Equivalent canonical candles with equivalent context and request therefore yield the same dataset fingerprint through provider-backed, `LOCAL_FIRST` and `LOCAL_ONLY` paths.

#### Research-configuration fingerprint v1

The effective Backtest research configuration contains, at minimum, the applicable dataset identity and request, strategy name and parameters, initial capital, effective risk-per-trade percentage, slippage percentage, slippage-enabled state and brokerage-enabled state. Callers supply effective risk per trade explicitly; fingerprinting does not introduce a second hidden default.

Replay/display controls, visualization, export controls and destinations, UI state, random session IDs, journal paths, source policy and provenance do not change research-configuration identity when canonical data is equal. Strategy-parameter mapping insertion order is irrelevant. Changing any effective result-affecting value changes configuration identity. M3.8c does not change runtime configuration propagation.

#### Stable Backtest-result fingerprint v1

Stable-result identity covers complete current `Trade` records, complete current `BarRecord` records and the canonical equity curve. It excludes `BacktestResult.session_id`. Trade content includes symbol, entry/exit times and prices, stop price, quantity, direction, exit reason, P&L, gross P&L, transaction cost and P&L percentage. Bar content includes timestamp, OHLCV, strategy, state, signal, execution event, execution price/quantity, decision snapshot, equity, cash, position size and drawdown.

Decision snapshots use the same recursive canonical-value contract; unsupported values fail rather than being stringified. Equivalent stable results with different session IDs have the same fingerprint, while changing a stable field changes identity. This fingerprints the current deterministic result contract and does not assert financial correctness, which remains M4 work.

#### Research evidence model and store

The immutable logical record contains an evidence ID, timezone-aware microsecond-precision creation time, explicit status, `DatasetContext`, requested `TimeRange`, dataset/configuration/result fingerprints, provenance, optional repository revision, concise summary and artifact references. Evidence ID identifies the persisted record and is not a reproducibility fingerprint. Evidence ID and creation time are excluded from the three fingerprints. Provenance may describe policy/provider origin without altering dataset identity.

Evidence status is one of `ACCEPTED`, `FAILED` or `INCOMPLETE`. `ACCEPTED` requires all three valid fingerprints. `FAILED` and `INCOMPLETE` may carry partial information but must never persist or reload as `ACCEPTED`. Detailed trades, bars and equity data may remain in referenced artifacts.

Initial persistence uses a dedicated SQLite database/file, logically and physically separate from the historical candle/coverage store. The minimal store saves one record, loads by evidence ID, preserves exact model round trips and supports durable reload through a fresh store instance. Duplicate evidence IDs fail explicitly without overwrite. Invalid `ACCEPTED` evidence fails before authoritative persistence. The logical record contract is frozen; the exact SQL layout and final database filename are not.

#### Ownership and boundary

Proposed M3.8c ownership is:

- `core/research/reproducibility.py` for canonical serialization and three fingerprint builders;
- `core/research/models/research_evidence.py` for evidence model/status contracts; and
- `core/research/sqlite_research_evidence_store.py` for dedicated SQLite persistence.

The placeholder `core/research/research_session.py` is not repurposed, and existing `ResearchRequest`/`ResearchResult` are not expanded merely to carry this capability. M3.8c builds independently testable identity and persistence primitives without real network access. It does not wire persistence into `run_backtest()`, HistoricalSource, main, WFA, API or frontend. M3.8d owns the explicitly authorized future fresh/local repeated-run integration.

This decision excludes Backtest economic validity, timing/fill/stop correctness, brokerage tax fidelity, WFA validity, paper/live behavior, the final research catalog, analytics warehouse, UI/API workflow, broker-session lifecycle, market-calendar/expected-bar completeness and real-money execution.

### AD-016 — Bar-based Backtest economic semantics v1

**Status:** ACCEPTED

**Target:** M4

AD-016 defines intended M4 Backtest semantics. It does not claim that current production implementation already satisfies them.

A strategy decision made after observing completed bar N cannot execute retrospectively on that bar. A queued market-style BUY or discretionary SELL may execute no earlier than bar N+1 open. If no next bar exists, the action remains unfilled, and end of data does not implicitly liquidate an open position. An open terminal position is marked to the final available close and its unrealized P&L remains part of final equity unless a separately configured research policy requires liquidation.

A queued long BUY uses the next open as its reference price, with BUY slippage applied exactly once when enabled. Its protective stop must be strictly below the actual entry fill or the entry is rejected explicitly. Once accepted at the open, the position exists for that bar and may be stopped by its later low.

For an existing long, a candle opening at or below the stop uses the open as the gap-through-stop reference. Otherwise a low reaching the stop uses the stop as the ordinary-stop reference. SELL slippage is applied exactly once to the selected reference. At the candle open, a protective gap stop has priority over a queued discretionary SELL; otherwise the queued SELL executes at the open, and ordinary intrabar stop evaluation follows only if the position remains open.

Execution and portfolio state are authoritative over strategy-local position belief. M4 must provide explicit agreement for accepted entry, rejected entry, strategy exit and forced/protective exit. Position sizing targets current pre-entry account equity and must also enforce available-cash affordability including entry transaction costs.

Instrument price return, gross monetary trade P&L, net monetary trade P&L and account/equity return remain distinct under AD-011. `Trade.pnl_pct` retains instrument-price-return meaning unless explicitly migrated and is not authoritative account return. Account return, performance and drawdown derive from authoritative portfolio/equity state rather than synthetic compounding of trade percentages. Detailed daily/weekly equity-risk, unrealized-P&L and session/reset semantics remain M4.5 work.

The configured simplified `BrokerageModel` must be applied exactly once where applicable, be independently enabled or disabled, and flow consistently into cash, trade P&L and account equity. This decision does not claim exact AngelOne, exchange, product or tax fidelity.

AD-015 v1, including `kanasu.backtest-config.v1`, remains frozen. M4 requires a versioned successor research-configuration identity containing an explicit Backtest economic/execution policy version and all effective result-affecting M4 settings. The successor schema identifier is intentionally not fixed by this decision.

## Decision workflow

Create or update an AD when a choice changes module ownership, a durable contract, persistence identity/schema, accounting semantics, runtime boundaries, or a cross-cutting non-functional rule. Record context, alternatives, consequences, scope and evidence. Accepted decisions may be superseded but are never erased or renumbered.
