# Kanasu Validation Plan

## 1. Purpose

This document owns subsystem Definitions of Done, evidence requirements and release gates. It distinguishes implementation, integration, validation and release readiness.

A passing focused test proves only the declared behavior under that test's conditions. It does not establish profitability, provider completeness, end-to-end integration or release readiness.

## 2. Evidence model

Each roadmap task should identify:

- the behavior and failure behavior being established;
- focused tests or other deterministic evidence;
- required integration and regression checks;
- relevant environment, dataset, configuration and revision;
- material limitations that remain; and
- affected authoritative documentation.

A task may be DONE only when its accepted evidence and required documentation synchronization are complete.

## 3. Subsystem Definitions of Done

### Candle and data contracts

- Valid and invalid OHLCV controls cover the declared contract.
- Timestamp fidelity, chronology, duplicates and timezone-awareness behavior are explicit at the relevant boundary.
- Rejected data cannot mutate accepted sequence state.
- No sorting, deduplication, localization, conversion, gap filling or repair occurs unless an accepted contract explicitly owns it.
- Source-specific parsing does not leak raw provider structures downstream.

### Storage

- Dataset and candle identity are explicit and deterministic.
- Round-trip fidelity covers supported timestamps and OHLCV.
- Range semantics and chronological reads are verified.
- Exact duplicates are idempotent and conflicting duplicates are rejected.
- Batch writes are genuinely atomic.
- Writes are durably visible to a new store instance.
- Schema evolution, backup and concurrency behavior are defined before operational reliance requires them.

### Coverage and retrieval

- Retrieval coverage has an explicit interval and evidence contract.
- Missing-range planning is deterministic and boundary behavior is tested.
- Stored candles are not mistaken for retrieval coverage.
- Retrieval coverage is not mistaken for expected-bar completeness.
- Empty, partial, failed and conflicting provider responses have explicit outcomes.
- Accepted candles and any resulting coverage claim remain transactionally consistent.
- Local-only behavior performs no provider authentication or network request.
- Returned candles pass the canonical integrity boundary.

### Execution and accounting

- Fill-price, slippage and explicit-cost ownership are tested.
- Open, mark and close accounting preserves portfolio invariants.
- Same-bar entry/stop causality and subsequent-bar stops are tested.
- Brokerage-enabled and disabled behavior are independent of slippage.
- Execution reporting uses actual simulated fills.
- Strategy, execution and portfolio position state cannot silently diverge.
- Stop/gap, affordability, sizing and drawdown semantics are documented and tested to the level required by the selected research strategy.

### Backtest

- A deterministic fixture produces known signals, trades and account results.
- Input dataset identity and effective strategy/execution/risk configuration are retained.
- Timing, fill, stop and end-of-data assumptions are explicit.
- Equity, drawdown and return metrics use the intended account basis.
- Repeated runs from the same manifest produce equivalent results.
- API and exported results originate from the actual engine rather than fixtures or placeholders.

### Walk-Forward Analysis

- Rolling and expanding windows terminate and match declared boundaries.
- In-sample selection never consumes out-of-sample observations.
- Capital, runtime economics, dataset identity and strategy parameters propagate unchanged unless explicitly varied.
- Metrics distinguish instrument, trade and account returns.
- Empty/insufficient samples and failed windows are represented truthfully.
- Overlapping out-of-sample windows and equity stitching have an explicit policy.
- Each selected parameter set and out-of-sample result is reproducible.

### Live market data

- One provider delivers canonical completed candles with declared timestamp semantics.
- Duplicates, regressions, conflicts and mixed awareness are handled explicitly.
- Freshness, disconnect, reconnect and partial-candle behavior are observable and tested.
- Diagnostic recording can reproduce relevant feed failures.
- A feed failure cannot be reported as a healthy running session.

### Paper runtime

- The session owns one feed/strategy/risk/simulated-execution/portfolio lifecycle.
- It consumes real market data for the V1 operational mode.
- Start, running, stopping, stopped and failed states reflect the actual runtime.
- Stop and end-of-stream behavior release resources predictably.
- Journals and snapshots reflect authoritative execution/portfolio state.
- Restart/recovery policy and unsupported cases are explicit.
- No real-money order route is reachable in V1.

### API

- Endpoints operate real authorized workflows or identify explicit mock/development responses.
- Request validation, errors, status and identifiers are stable and tested.
- Reported job/session state matches actual backend state.
- Long-running work has a defined lifecycle and cancellation policy.
- Deployment security and authorization match the exposure of the service.

### Frontend

- Displayed metrics and states come from authoritative API responses.
- Loading, empty, error, stopped and failed states are visible.
- Backtest and paper modes are labelled accurately.
- Core workflows work at supported desktop and mobile-browser sizes.
- Setup/build/lint instructions match package scripts.
- Placeholder UI cannot be mistaken for validated product behavior.

### Documentation

- One authoritative owner exists for each fact.
- Current, target and historical statements are clearly labelled.
- Permanent IDs and historical crosswalks are preserved.
- Relative links resolve and moved paths have no active references.
- Project Status records dated evidence without claiming checks that were not run.
- Architecture decisions and deferred issues reflect material contract changes.

### Eventual V2 live execution

- Broker order acknowledgement, rejection, cancellation and partial/full fill lifecycles are verified.
- Client/order identity and retries are idempotent.
- Broker orders, fills, positions, cash and charges reconcile with local state.
- Restart and unknown-state recovery are tested.
- Stale feeds, disconnects and broker failures trigger defined safe behavior.
- Exposure limits, operator stop controls and restricted rollout are verified.
- Applicable broker, exchange and regulatory requirements are reviewed and accepted.

<a id="m36b-coverage-and-missing-range-planning"></a>

## 4. M3.6b — Coverage and missing-range planning

M3.6b deals only with retrieval coverage and deterministic missing-range planning. Request, coverage and returned missing ranges use half-open `[start, end)` intervals: start is included and end is excluded. It excludes broker/provider wiring, SQLite orchestration, expected-bar generation, market or holiday calendars, timezone conversion, arbitrary naive/aware normalization and source-policy implementation.

The planner contract does not change SQLiteCandleStore.load(), whose candle-read range is inclusive at both ends. Any adapter between those semantics belongs to M3.6c.

Required focused cases:

1. No coverage returns the requested interval.
2. Full coverage returns no missing interval.
3. Coverage entirely before the request does not reduce it.
4. Coverage entirely after the request does not reduce it.
5. Partial coverage at the beginning leaves the uncovered end.
6. Partial coverage at the end leaves the uncovered beginning.
7. An internal covered interval produces two missing intervals.
8. Multiple disjoint covered intervals produce all missing intervals.
9. Overlapping coverage intervals are reconciled for planning.
10. Touching intervals are continuous coverage under the half-open convention.
11. Nested intervals do not create false gaps.
12. Duplicate intervals do not change the result.
13. Unordered intervals are accepted and normalized deterministically.
14. Coverage extending outside the request is clipped to the request.
15. Exact request-start and request-end boundaries obey `[start, end)`.
16. Invalid request or coverage intervals are rejected explicitly.
17. Incompatible naive/aware timestamps produce a clear error rather than implicit conversion.

Acceptance evidence must show that returned missing ranges are chronological, non-overlapping and non-empty. It must not infer expected market bars from coverage.

<a id="m36c-local-first-historical-retrieval-service"></a>

## 5. M3.6c — Local-first historical retrieval service

M3.6c composes persistent retrieval coverage, the M3.6b planner, an injected provider contract, and local candle persistence. Service requests and provider coverage use half-open `[start, end)` intervals. `SQLiteCandleStore.load()` remains inclusive at both ends; the service adapter excludes a candle exactly at the request end without using a datetime epsilon or timeframe duration.

Required focused evidence:

1. A fully covered request, including sparse or confirmed-empty local data, makes no provider call.
2. Stored candles without retrieval coverage still require provider evidence.
3. Partial coverage and multiple coverage islands request only the planned missing gaps.
4. Full provider success persists candles and explicit coverage for reuse by a fresh store/service instance.
5. Confirmed-empty coverage is persisted without inferring expected bars.
6. A partial provider result persists only its claimed coverage, reports the remaining gaps, and a later call requests only those gaps.
7. Provider failure or missing coverage evidence creates no false coverage claim.
8. Coverage outside the requested gap, candles outside the gap or explicit coverage, incompatible timezone awareness, and malformed candle sequences are rejected before persistence.
9. Exact stored candle overlap is idempotent; conflicting overlap rolls back new candles and coverage from that provider result.
10. Candle and coverage state remain isolated by complete `DatasetContext` identity.
11. SQLite candle and coverage writes are transactional and durably visible across instances.
12. SQLite inclusive reads filter and order parsed datetimes with Python comparison semantics across aware offsets, reject naive/aware incompatibility clearly, and preserve timestamp offsets and precision without conversion. Each `DatasetContext` persists one awareness style across candle and coverage timestamps, while differing aware offsets remain valid. Equivalent aware timestamps with different serialized offsets form one candle identity while retaining the first stored representation; conflicting OHLCV is rejected transactionally.
13. The half-open service result includes the request start and excludes the request end while leaving the inclusive store API unchanged.

Acceptance evidence must confirm that M3.6c adds no broker authentication, provider construction, runtime source-policy selection, expected-bar logic, calendar/session inference, or timestamp normalization. DW-010 remains open until closure review determines the documented local-store compatibility concern is fully resolved in its intended scope.

## 6. V1 release gates

V1 is release-ready only when all mandatory gates pass:

- trusted historical local-first retrieval and parity;
- reproducible dataset/configuration identity;
- validated backtest timing/economics/account metrics;
- validated WFA windows, propagation and metrics;
- operational real-market-data paper ingestion;
- truthful paper-session lifecycle and authoritative portfolio state;
- durable journals/results adequate for investigation;
- real API workflows and responsive UI;
- documented limitations and failure behavior; and
- an explicit confirmation that real-money execution is unavailable.

Progress in one gate cannot compensate for a failed mandatory gate.
