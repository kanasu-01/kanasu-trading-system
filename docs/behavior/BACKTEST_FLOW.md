# Kanasu Backtest Behavioral Flow

## Purpose

This document describes the current authoritative M8 Backtest path in natural language.

It is intentionally about behavior and decisions rather than Python implementation syntax.

## BT-FLOW-001 ? User starts a Backtest

**Status:** VERIFIED

~~~text
User opens Backtest
        |
        v
Frontend asks backend for supported choices
        |
        v
User chooses:
- symbol
- timeframe
- strategy
- start/end
- initial capital
- strategy parameters
- timezone
        |
        v
User submits Backtest
        |
        v
Backend validates request
        |
        v
Application creates effective Backtest configuration
and DatasetContext
        |
        v
Application creates configured historical source
        |
        v
Historical-source policy decides how data is obtained
        |
        v
Application creates selected strategy
        |
        v
Authoritative Backtest runtime retrieves candles
        |
        v
BacktestEngine runs validated strategy/execution/
risk/portfolio semantics
        |
        v
BacktestResult is produced
        |
        v
Backend derives authoritative summary metrics
        |
        v
Backend returns run ID, summary,
equity curve and completed trades
        |
        v
Frontend presents backend result
~~~

The frontend does not independently reconstruct authoritative account P&L, equity or drawdown for this Backtest result.

## DATA-FLOW-001 ? Historical-source decision

**Status:** VERIFIED

~~~text
Historical candles requested
        |
        +-- LOCAL_ONLY
        |      |
        |      +-- trusted local coverage complete
        |      |       -> load local candles
        |      |
        |      +-- coverage incomplete
        |              -> fail with incomplete coverage
        |
        +-- LOCAL_FIRST
        |      |
        |      +-- trusted local coverage complete
        |      |       -> load local candles
        |      |       -> do not create provider
        |      |
        |      +-- coverage incomplete
        |              -> create provider lazily
        |              -> fetch missing ranges
        |              -> validate provider result
        |              -> persist accepted data/coverage
        |              -> load canonical result
        |
        +-- PROVIDER_BACKED
               |
               -> create required provider
               -> request historical data
               -> validate provider result/coverage
               -> reject incomplete coverage
               -> persist accepted data/coverage
               -> load canonical result
~~~

The Backtest therefore does not simply "check whether the broker is connected" before every run. Broker/provider capability is required only when the configured source policy and local coverage require external historical data.

## BT-FLOW-002 ? Backtest execution authority

**Status:** VERIFIED

Historical retrieval returns canonical candles to the authoritative Backtest runtime.

The runtime constructs `BacktestEngine` with the selected strategy, initial capital, runtime risk/economic context and dataset context.

The engine owns the validated M4 execution lifecycle. Results flow back through `BacktestResult`; the API projects that result rather than inventing a separate frontend accounting model.

## Important failure branches

A Backtest may stop before financial execution when:

- request validation rejects unsupported or malformed inputs;
- required local historical coverage is incomplete under LOCAL_ONLY;
- external provider capability is required but cannot be created/authenticated;
- provider retrieval fails;
- provider evidence does not cover the requested interval;
- canonical candle/data validation fails;
- strategy/configuration construction fails;
- an execution/accounting invariant fails.

Operational failure must not be described as strategy rejection. M9 introduces separate research qualification semantics above this computation path.

## Primary trace

Current implementation includes:

- `frontend/src/pages/BacktestPage.tsx`
- `api/routes/backtest_routes.py`
- `api/backtest_application.py`
- `core/market_data/historical_source_factory.py`
- `core/market_data/historical_source.py`
- `core/runtime/backtest_runtime.py`
- authoritative Backtest/execution/risk/portfolio components beneath the runtime

Key independently checked verification examples include:

- `test_local_first_returns_warm_cache_without_factory`;
- `test_local_only_reports_exact_missing_ranges_without_factory`;
- `test_backtest_queues_completed_bar_signals_for_following_open`;
- `test_backtest_reports_authoritative_execution_portfolio_state`; and
- frontend `BacktestPage.test.tsx` ? `submits the authoritative request and renders the response`.

Additional accepted M3/M4/M8 regression evidence remains applicable to the deeper execution, risk, accounting and application contracts.
