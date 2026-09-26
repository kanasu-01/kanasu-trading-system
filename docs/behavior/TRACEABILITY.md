# Kanasu Behavioral Traceability

## Purpose

Behavioral traceability lets the product owner review meaningful system behavior in natural language while technical review verifies that implementation and tests actually match that behavior.

It does not replace source-code review, automated tests or specialist inspection for numerical, concurrency, security or resource-management defects.

## Stable identifiers

Use durable identifiers by area:

- `DATA-FLOW-*`, `DATA-RULE-*`
- `BT-FLOW-*`, `BT-RULE-*`
- `WFA-FLOW-*`, `WFA-RULE-*`
- `PAPER-FLOW-*`, `PAPER-RULE-*`
- `RESEARCH-FLOW-*`, `RESEARCH-RULE-*`
- `SAFETY-RULE-*`

Do not silently renumber accepted identifiers. A superseded item keeps its ID and points to the replacement.

## Verification states

A behavior is:

- `DESIGNED` when its intended contract is accepted;
- `IMPLEMENTED` when implementation exists but trace verification is incomplete;
- `VERIFIED` only after implementation and appropriate test/evidence traces are checked;
- `DEFERRED` when deliberately outside current scope;
- `SUPERSEDED` when replaced while preserving history.

Documentation text alone cannot establish `VERIFIED`.

## Required change declaration

Every implementation slice from M9.2 onward declares exactly one primary impact:

~~~text
BEHAVIOR IMPACT: NONE
BEHAVIOR IMPACT: ADDED
BEHAVIOR IMPACT: CHANGED
BEHAVIOR IMPACT: REMOVED
~~~

For non-`NONE` impact, record:

- affected behavior IDs;
- behavior before;
- behavior after;
- rationale;
- user/research impact;
- implementation paths/symbols;
- tests/evidence proving the behavior;
- adjacent invariants that must remain unchanged.

`BEHAVIOR IMPACT: NONE` is also reviewable. If code changes meaningful behavior, the declaration must be corrected before acceptance.

## Review gate

~~~text
accepted behavior before
        |
        v
authorized implementation
        |
        v
behavior after
        |
        v
natural-language behavior delta
        |
        v
implementation trace
        |
        v
test/evidence trace
        |
        v
independent deviation review
        |
        v
product-owner behavioral review
~~~

## Initial traceability map

| Behavior ID | Natural-language behavior | Primary implementation evidence | Verification evidence | Status |
|---|---|---|---|---|
| DATA-RULE-001 | Missing history is not silently invented | `core/market_data/historical_source.py`, historical retrieval/coverage boundaries | `test_local_only_reports_exact_missing_ranges_without_factory`; `test_old_local_coverage_cannot_mask_partial_provider_evidence` | VERIFIED |
| DATA-RULE-002 | Fully covered LOCAL_FIRST avoids provider creation | `HistoricalSource._retrieve_local_first()` | `test_local_first_returns_warm_cache_without_factory` | VERIFIED |
| BT-RULE-001 | Completed-bar decisions follow accepted next-interval execution | Backtest execution/engine boundaries | `test_backtest_queues_completed_bar_signals_for_following_open` | VERIFIED |
| BT-RULE-002 | Backend execution/portfolio state owns financial truth | execution/portfolio/Backtest result boundaries | `test_backtest_reports_authoritative_execution_portfolio_state`; frontend `BacktestPage.test.tsx` ? `submits the authoritative request and renders the response` | VERIFIED |
| WFA-RULE-001 | OOS does not select preceding parameters | `core/walk_forward/runner.py`, window/optimizer boundaries | `test_m5_5_end_to_end_wfa_validity_chain`; accepted M5 window/runner regression | VERIFIED |
| PAPER-RULE-001 | Clock alone cannot create a Paper fill | Paper processor/live runtime | `test_wall_clock_does_not_advance_source_event_watermark`; `test_clock_advance_alone_cannot_execute_pending_live_intent` | VERIFIED |
| PAPER-RULE-002 | Historical reconciliation cannot create retrospective Paper trades | live Paper reconciliation path | `test_live_reconciliation_replays_history_without_creating_trade_intent`; `test_live_reconciliation_with_open_position_uses_history_for_state_only` | VERIFIED |
| SAFETY-RULE-001 | Supported V1 application has no real-money order path | M8 application composition and dormant/unimplemented live path | M8 validation evidence | VERIFIED |
| RESEARCH-RULE-001 | Tested research lineage is retained | future M9 research catalog | future M9 tests | DESIGNED |
| RESEARCH-RULE-002 | Policy changes do not rewrite evidence | future qualification service | future M9 tests | DESIGNED |
| RESEARCH-RULE-003 | Execution success and research qualification are distinct | future M9 state model | future M9 tests | DESIGNED |
| RESEARCH-RULE-004 | Independent universe accounts are not presented as a portfolio | future Study aggregation | future M9 tests | DESIGNED |
| RESEARCH-RULE-005 | Candidate progression preserves exact lineage and WFA-before-Paper stage order | future Candidate/WFA/Paper application services | future M9 tests | DESIGNED |
| RESEARCH-RULE-006 | Universe quality constrains historical claims | future universe/data catalog | future M9 tests | DESIGNED |

Exact test names and symbol-level references should be tightened whenever a row is independently audited or affected by an implementation change.
