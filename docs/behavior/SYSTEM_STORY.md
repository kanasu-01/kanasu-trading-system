# Kanasu V1 Behavioral System Story

## Purpose

This document explains Kanasu V1 in natural language. It describes meaningful user/system behavior rather than implementation syntax.

Behavior becomes verified only through the rules in [TRACEABILITY.md](TRACEABILITY.md).

## V1 research story

~~~text
Open Kanasu
    |
    v
Create or reopen a Research Study
    |
    v
State the research intent / hypothesis
    |
    v
Choose a universe or instrument set
    |
    v
Choose strategy, timeframe, period,
parameters/search space, capital,
risk/economic assumptions and qualification policy
    |
    v
Register a frozen Study revision
    |
    v
Register all planned Trials
    |
    v
Resolve and validate data
    |
    v
Execute independent per-instrument experiments
    |
    v
Persist results and research evidence
    |
    v
Inspect Study-level distributions
and individual instrument results
    |
    v
Evaluate robustness and qualification
    |
    +--> rejected / insufficient / invalid
    |
    +--> eligible
             |
             v
       Freeze Candidate revision
             |
             v
       Run registered WFA / OOS procedure
             |
             v
       Qualification decision
             |
             +--> rejected / insufficient
             |
             +--> eligible for Paper
                        |
                        v
                 Start PaperCampaign
                        |
                        v
                 Observe one or more
                 real-data PaperSessions
                        |
                        v
                 Research decision
~~~

## V1 product boundary

V1 is single-user research for NSE cash equities.

Supported execution timeframes are 5m and 15m.

Trading is long-only, unlevered and simulated.

Universe research runs independent simulated accounts per instrument. Aggregate research describes breadth and distributions; it is not a shared-capital portfolio.

Paper uses real market data and simulated execution.

Real-money execution, leverage, short selling, derivatives and true shared-capital multi-symbol portfolio economics are outside V1.

## Existing validated foundations

M9 reuses the accepted historical-source, Backtest, risk/accounting, WFA, live-market-data and Paper-runtime cores.

M9 primarily adds persistent research workflow, evidence governance, universe/data truthfulness, qualification, Candidate lineage, PaperCampaigns and complete research UX around those foundations.
