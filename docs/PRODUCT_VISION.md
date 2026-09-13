# Kanasu Product Vision

## Purpose

Kanasu is a single-user, professional trading research system intended to make market data, strategy experiments, simulated execution, portfolio accounting, and evidence inspectable and reproducible. It is Python-first, modular, and broker-aware without allowing broker-specific formats to leak through the research core.

The initial market is NSE equities. The near-term research focus includes intraday strategies and multi-session holding horizons. Candle timeframe, indicator lookback, and intended holding horizon must be stated separately in research results.

## V1 — Research and Real-Market-Data Paper Trading

V1 should provide:

- trustworthy reusable historical data;
- local-first historical retrieval;
- reproducible dataset and configuration identity;
- deterministic, validated backtesting;
- validated Walk-Forward Analysis;
- strategy and parameter research;
- real market-data ingestion;
- simulated execution and authoritative simulated portfolio state;
- a truthful paper-session lifecycle;
- journals and reproducible results;
- real API workflows; and
- a responsive desktop and mobile-browser interface.

V1 explicitly excludes real-money broker execution. A research result or passing test does not establish profitability or readiness to risk capital.

## V2 — Controlled Real-Money Execution

V2 may begin only after V1 acceptance evidence supports it. It introduces real broker order submission, acknowledgements and rejections, cancellation and partial-fill handling, stable order identity and idempotency, broker reconciliation, restart recovery, cash/position/order reconciliation, operational safety controls, restricted rollout, and the applicable broker, exchange, and regulatory acceptance requirements.

Detailed permanent V2 milestone numbers are intentionally unallocated.

## Progressive future horizons

V3+ directions are candidates, not implementation claims or detailed commitments:

- multi-symbol research, capital allocation, exposure and correlation controls;
- scanners, technical market structure, volume/profile research, sector and relative-strength analysis;
- company news, event, fundamental and alternative-data research with point-in-time data controls;
- additional brokers and, when justified, additional markets;
- futures and options only after contract, expiry, multiplier, margin, rollover, exercise, settlement, and liquidity semantics are designed;
- statistical and ML research only after trustworthy data and leakage-resistant evaluation exist;
- AI assistance as an explainable research layer bounded by deterministic risk controls;
- an optional multi-user product only if demand, market-data rights, security, operations, and support justify it; and
- native mobile as a final major interface stage after stable APIs and validated responsive-web workflows.

## Intelligence and research tracks

Potential research areas include support/resistance and market-structure analysis, trend and breakout quality, momentum and volatility regimes, volume and observable flow proxies, historical-condition probability studies, news and event classification, social/alternative-data research, trade-quality models, adaptive strategy selection, and risk-adjusted opportunity ranking.

These remain research until each has a stated hypothesis, data prerequisites, deterministic baseline, evaluation method, failure criteria, and evidence. Claims such as “institutional” or “big-money” activity must be tied to measurable observables rather than inferred labels.

## Product principles

- Correctness, reproducibility, and explainability precede feature count.
- One authoritative owner exists for each trading/accounting fact.
- Current implementation, intended architecture, validation, and release readiness are stated separately.
- New infrastructure is introduced only when a concrete workflow needs it.
- The browser UI controls and observes backend workflows; it does not reconstruct trading or account state.
