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

## M9.2 first implementation layer

Before the complete registered Study workflow is introduced, M9.2 designs the lower-level durable execution/evidence substrate around the existing Backtest application.

A current application Backtest can therefore gain an immutable ExperimentSpec, a distinct RunAttempt, stable result/manifest artifacts and ResearchEvidence without being falsely represented as a Trial that was registered beforehand.

M9.4 now implements the accepted registered Study workflow above M9.2/M9.3 foundations: immutable StudyRevision registration creates the complete finite Trial population before execution; durable bounded ResearchJobs own queue progress; exact compatible prior evidence may be reused without rewriting its historical execution time; retries append job/attempt/disposition lineage; cancellation and restart recovery remain truthful; and Study aggregation reports independent-account distributions with explicit denominators. The backend application/API exposes creation, registration, inspection, Start and cancellation, while actual queue draining still requires an explicit authoritative execution-input handler rather than inventing provider mappings. Qualification remains M9.5 scope and complete research-workspace frontend integration remains M9.8 scope.
