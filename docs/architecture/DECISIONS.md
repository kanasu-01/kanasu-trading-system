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

Instrument price return, gross monetary trade P&L, net monetary trade P&L and account/equity return are different measures. `Trade.pnl_pct` retains instrument-price-return meaning. Research and risk reporting choose the measure matching the question and must not use `Trade.pnl_pct` as a substitute for account return. No separate gross-trade-return or net-trade-return percentage concept is required by this decision.

Authoritative Backtest reporting uses `PerformanceMetrics.summarize_backtest(result: BacktestResult)`. Its trade-level terminology distinguishes net-profitable, net-losing and net-breakeven completed trades; positive, negative and mean instrument return; gross and net realized monetary P&L; monetary mean net P&L per completed trade; and completed-trade transaction-cost total. Account P&L, account return and maximum equity drawdown are derived separately from authoritative equity. `mean_instrument_return_pct` is not account expectancy, while `mean_net_pnl_per_completed_trade` is monetary expectancy per completed trade.

The existing `PerformanceMetrics.summarize(trades)` is a bounded legacy trade-only compatibility path for current WFA callers. After M4.4, Backtest reporting must not use it. WFA metric migration and validity remain M5 work, so this compatibility decision does not validate WFA economics.

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

#### M4.3 execution-phase and ownership refinement

This refinement is accepted target design and does not claim implemented behavior. Backtest orchestration owns one pending market-style intent between candles. The intent retains the signal and decision-time context required to execute on the next candle without using future information from that candle.

For each candle, the Backtest first processes the pending intent and protective execution against authoritative portfolio state, then delivers ordered execution feedback, marks any remaining open position to the completed candle close, lets the strategy evaluate that completed candle, and stores any resulting intent for the next candle. Bar recording follows feedback/state convergence and may contain an execution caused by the previous bar together with a new signal from the current bar.

A queued BUY uses the execution-bar open and applies BUY slippage exactly once. Its stop is derived from decision-time information: a supplied rejection midpoint or the existing 2% fallback based on the signal-bar close. A stop at or above the actual entry fill rejects the entry with `INVALID_ENTRY`. After an accepted open-time entry, the same bar's later low may cause an ordinary protective exit at the stop reference, yielding ordered `ENTRY_ACCEPTED` then `PROTECTIVE_EXIT` feedback. The new entry does not receive gap-stop treatment at its entry open.

For an already-open long, the deterministic priority is gap protective stop at the candle open, then queued discretionary SELL at the open, then ordinary intrabar protective stop at the stop price. A gap protective exit consumes a queued SELL without producing a second exit. BUY while authoritative LONG and SELL while authoritative FLAT remain explicit state violations, except that the superseded valid SELL is not contradictory.

Current candle close, high and low cannot influence open-time execution. The low is used only for later intrabar stop evaluation. Close marking occurs only after execution/protective processing and only if a position remains open. A final-bar decision remains pending and unfilled; no final-close execution or automatic liquidation is manufactured, while any still-open position is marked to the final close.

Ordered AD-017 feedback remains authoritative when multiple events occur. Singular execution-event, price and quantity fields remain final-event diagnostics, and M4.3 does not change `BarRecord` or `BacktestResult` schemas.

#### M4.4 account-performance refinement

This refinement is accepted target design and does not claim implemented behavior. Authoritative Backtest metrics receive the complete `BacktestResult` rather than completed trades alone. For a normal non-empty canonical Backtest under the M4.3 lifecycle, starting equity is the first `BarRecord.equity` because no prior-bar execution can exist before that record, and ending equity is the last `BarRecord.equity`. Account P&L is ending minus starting equity; account return percentage is account P&L divided by starting equity and multiplied by 100. This is the current canonical Backtest contract, not a universal assumption for future seeded-position or preloaded-state Backtests.

Transaction costs, realized P&L and final unrealized marked P&L participate through authoritative equity, and zero completed trades do not suppress account metrics. Empty no-bar/no-trade results report zero account P&L, return and drawdown. Trades without equity records are inconsistent and fail explicitly. A non-empty curve requires finite equity throughout and finite, strictly positive starting equity. M4.4 adds no `initial_capital` field to `BacktestResult` and leaves frozen AD-015 v1 unchanged.

Maximum equity drawdown evaluates every authoritative equity point from an initial peak equal to starting equity. Each point contributes `(peak - equity) / peak * 100` after updating the peak; the greatest result is reported as a non-negative loss magnitude. Empty and single-point curves report zero, recovery does not erase an earlier maximum, and negative equity may produce drawdown greater than 100% without clipping. Authoritative Backtest drawdown never uses compounded `Trade.pnl_pct`.

The authoritative metric names are `completed_trade_count`, `net_profitable_trade_count`, `net_losing_trade_count`, `net_breakeven_trade_count`, `net_profitable_trade_rate_pct`, `mean_positive_instrument_return_pct`, `mean_negative_instrument_return_pct`, `mean_instrument_return_pct`, `gross_realized_pnl`, `net_realized_pnl`, `mean_net_pnl_per_completed_trade`, `completed_trade_transaction_cost_total`, `account_pnl`, `account_return_pct` and `max_equity_drawdown_pct`. For zero completed trades, the trade counts, rates, means, realized totals and per-trade expectancy are zero, while account metrics still derive from equity. Calculations remain full precision programmatically and presentation owns rounding. Ambiguous `avg_win_pct`, `avg_loss_pct`, `expectancy_pct` and synthetic `max_drawdown_pct` do not represent authoritative Backtest metrics; they may remain temporarily only within the legacy WFA compatibility path until M5.

Execution and portfolio state are authoritative over strategy-local position belief. M4 must provide explicit agreement for accepted entry, rejected entry, strategy exit and forced/protective exit. Position sizing targets current pre-entry account equity and must also enforce available-cash affordability including entry transaction costs.

Instrument price return, gross monetary trade P&L, net monetary trade P&L and account/equity return remain distinct under AD-011. `Trade.pnl_pct` retains instrument-price-return meaning unless explicitly migrated and is not authoritative account return. Account return, performance and drawdown derive from authoritative portfolio/equity state rather than synthetic compounding of trade percentages. AD-018 records the accepted M4.5 target for daily/weekly equity-risk, unrealized-P&L and session/reset semantics; production implementation remains pending.

The configured simplified `BrokerageModel` must be applied exactly once where applicable, be independently enabled or disabled, and flow consistently into cash, trade P&L and account equity. This decision does not claim exact AngelOne, exchange, product or tax fidelity.

AD-015 v1, including `kanasu.backtest-config.v1`, remains frozen. M4 requires a versioned successor research-configuration identity containing an explicit Backtest economic/execution policy version and all effective result-affecting M4 settings. The successor schema identifier is intentionally not fixed by this decision.

### AD-017 — Execution feedback and strategy-state authority v1

**Status:** ACCEPTED

**Target:** M4.2

AD-017 defines intended M4.2 design authority. It does not claim that the contract is implemented or validated.

Strategy signals are intents rather than proof of execution. `TradeExecutionEngine` and `PortfolioManager` own authoritative position truth. Strategy-local state changes from execution feedback after the authoritative outcome, not merely because BUY or SELL was emitted.

Execution feedback is typed, immutable and ordered. Its logical event types are `ENTRY_ACCEPTED`, `ENTRY_REJECTED`, `STRATEGY_EXIT` and `PROTECTIVE_EXIT`. An event carries its type, symbol, timestamp, authoritative position state after the event, and applicable fill price, quantity or machine-readable rejection reason. Current implemented rejection classes include drawdown-limit, invalid-quantity or invalid-entry conditions, and portfolio-risk rejection. AD-018 accepts future M4.5 extension with `INSUFFICIENT_CASH`; that target does not claim implementation.

The feedback path is `TradeExecutionEngine` → `BacktestEngine` → `StrategyRunner` → an optional BaseStrategy execution-feedback hook. The hook defaults to a no-op for compatibility. `TradeExecutionEngine` does not directly mutate strategy-local state. A feedback-handler failure fails the Backtest explicitly rather than allowing execution and strategy state to diverge silently.

The contract supports multiple ordered events within one candle and must not impose a one-event-per-candle limitation. In particular, future M4.3 timing may produce `ENTRY_ACCEPTED` followed by `PROTECTIVE_EXIT` on the same bar. Contradictory validated-research states fail explicitly when they indicate disagreement, including BUY while authoritative state is LONG or SELL while authoritative state is FLAT.

`SMACrossOverStrategy` is the M4.2 reference strategy. Emitting BUY does not set its local position open; `ENTRY_ACCEPTED` does, while `ENTRY_REJECTED` leaves or sets it flat. Emitting SELL does not set it flat before execution; `STRATEGY_EXIT` and `PROTECTIVE_EXIT` do. PivotBoss remains unvalidated and outside M4.2 validated strategy scope.

### AD-018 — Backtest current-equity sizing and period-loss guards v1

**Status:** ACCEPTED

**Target:** M4.5

AD-018 refines AD-001, AD-002 and AD-016; it does not supersede them. It defines accepted M4.5 Backtest target design and does not claim that production implementation or validation already satisfies the contract. AD-015 v1 remains frozen.

#### Current-equity sizing

`PortfolioManager` equity and cash are authoritative. A Backtest long entry sizes from authoritative current pre-entry equity sampled immediately before entry mutation. Risk budget is `sizing_equity * risk_per_trade_pct / 100`; price risk per share is actual entry fill after configured BUY slippage minus the stop retained from the prior completed-bar decision; risk quantity is the floor of risk budget divided by price risk; max-position notional is `sizing_equity * max_position_pct / 100`; max-position quantity is its floor after division by actual fill; and the candidate quantity is the smaller result.

Initial capital does not remain the sizing denominator after account equity changes. Current candle high, low and close cannot affect open-time sizing. A long stop must be strictly below actual fill. Equity, prices and risk inputs must be finite; `risk_per_trade_pct` and `max_position_pct` must be finite and strictly positive; zero/negative equity and a quantity below one produce no valid entry. The existing fixed-construction-capital RiskManager path may remain temporarily for excluded legacy callers, but Backtest must use an explicitly current-equity-aware boundary.

AD-018 does not impose `max_position_pct <= 100` as a configuration invariant. Available-cash affordability is the final unlevered safety boundary, so a configured value above 100 cannot authorize spending beyond authoritative cash.

#### Available-cash affordability

Risk-distance sizing, max-position sizing and affordability are separate constraints. For integer quantity `q`, notional is actual entry fill multiplied by `q`. When brokerage is enabled, required cash is notional plus `BrokerageModel.calculate(notional).total_cost`; when disabled, required cash is notional. Accepted quantity is the largest affordable integer quantity not exceeding the sizing candidate and must satisfy required cash less than or equal to authoritative available cash.

The current monotonic BrokerageModel permits deterministic binary search, but the durable decision is the selected largest affordable result, not the search mechanism. Search-time cost calculations are pure; only final accepted entry cost is charged exactly once. When no quantity of at least one is affordable, entry is rejected without portfolio mutation using `ExecutionRejectionReason.INSUFFICIENT_CASH`. `PortfolioManager` defensively rejects an unaffordable long entry if execution violates the pre-check. An accepted unlevered long entry cannot create negative authoritative cash.

#### Period-start-equity loss guards

Daily and weekly Backtest guards use period-start authoritative equity rather than period peak-to-current drawdown:

~~~text
period_loss_pct = max(
    0,
    (period_start_equity - current_equity)
    / period_start_equity
    * 100
)
~~~

Daily baseline is authoritative equity carried into the first observed candle of a represented date. Weekly baseline is authoritative equity carried into the first observed candle of a represented `(ISO year, ISO week)`. Gains do not raise or reset either baseline. Realized P&L, unrealized marked P&L and transaction costs enter only through authoritative equity; the Backtest path does not additionally accumulate `Trade.pnl` or trade-return percentages.

Loss equal to or greater than its configured threshold is a breach. A daily or weekly breach blocks new entries only and latches for the remainder of that period; recovery does not reopen entries. Exits and protective stops remain allowed, and no forced liquidation is introduced. A new date resets only daily baseline/latch, a new ISO-year/week resets weekly baseline/latch, and simultaneous transitions reset both as applicable. Negative account equity may produce loss greater than 100% without clipping. Non-finite observed equity is an invariant failure. Non-positive period-start equity latches the affected period without division.

M4.4 historical `max_equity_drawdown_pct` remains a separate account-reporting concept and is not the M4.5 entry guard.

#### Candle-calendar boundaries

Daily identity is `candle.timestamp.date()` and weekly identity is represented `(ISO year, ISO week)`. Naive timestamps use represented naive fields; aware timestamps use represented local fields. AD-018 does not localize or convert timestamps, change `DatasetContext` timezone semantics, infer holidays, create synthetic missing sessions or imply an exchange calendar. Sparse data transitions on the first observed candle with a different period identity.

For a position carried across a boundary, the new baseline is authoritative equity carried from the prior completed/marked bar before the new candle's open-time execution. Consequently, a gap-stop economic effect after the transition belongs to the new period.

#### No-lookahead state ordering

AD-016/M4.3 execution priority remains authoritative. Each Backtest candle begins from portfolio state carried from the prior completed bar. Period initialization or transition uses only current timestamp and carried equity. A pending BUY first respects existing latches, determines actual open fill, validates the prior-decision stop, samples current pre-entry equity and cash, calculates risk/max-position quantity and enforces affordability.

After accepted entry, the position and entry cost mutate authoritative portfolio state once and the resulting equity is then observed. After exit, fill/cost are determined, `PortfolioManager` closes first and authoritative post-close equity is then observed without separately adding trade P&L. Gap stop, queued discretionary SELL, ordinary stop, same-bar post-entry protection and ordered feedback remain unchanged. A surviving open position is marked to current close; post-mark equity is observed; only then does the strategy evaluate the completed candle and queue its next intent. Current candle high, low and close never influence a current-open entry except that the later low retains its accepted M4.3 protective-stop role after entry.

#### Configuration and failure contract

Canonical Backtest effective risk propagates `AppConfig.risk_per_trade_pct` through a compatible `RuntimeContext` setting to `BacktestEngine` and `TradeExecutionEngine`. M4.5 does not duplicate the setting in `BacktestConfig`. WFA-specific risk/configuration propagation remains M5 work, although WFA may inherit corrected shared Backtest mechanics because it uses `BacktestEngine`; this inheritance does not validate WFA economics and does not justify a deliberately incorrect legacy Backtest fork.

Accepted rejection meanings are: `INVALID_ENTRY` for missing/invalid long stop or stop not strictly below actual fill; `INVALID_QUANTITY` when equity/risk sizing produces no valid quantity; `DRAWDOWN_LIMIT` when a daily/weekly equity-loss latch blocks entry; existing `PORTFOLIO_RISK_LIMIT`; and `INSUFFICIENT_CASH` when otherwise-legitimate sizing cannot fund one share including enabled entry cost. Non-finite authoritative equity, cash, fill or transaction cost is an invariant failure rather than a normal rejection. Rejection leaves authoritative cash, position state, completed trades and transaction-cost accounting unchanged. Execution diagnostics, including `last_transaction_cost`, reset before every attempt.

#### Consequences and scope

M4.5 production must preserve authoritative portfolio ownership, explicit fill/cost ownership, M4.2 strategy/execution agreement, M4.3 no-lookahead ordering and M4.4 reporting semantics. PaperRuntime and broker/live risk-policy migration, WFA validity/configuration migration, multi-symbol risk redesign, exchange session/holiday calendars, exact broker/exchange/tax fidelity, leverage, margin, shorts, derivatives, forced liquidation, PivotBoss or obsolete standalone-script repair, API/frontend changes, M4.6 successor identity and M4.7 integration are excluded from validated M4.5 scope.

## Decision workflow

Create or update an AD when a choice changes module ownership, a durable contract, persistence identity/schema, accounting semantics, runtime boundaries, or a cross-cutting non-functional rule. Record context, alternatives, consequences, scope and evidence. Accepted decisions may be superseded but are never erased or renumbered.
