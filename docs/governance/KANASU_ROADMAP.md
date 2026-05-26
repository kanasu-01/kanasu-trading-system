# KANASU MASTER ROADMAP

## Purpose

This document defines the permanent implementation order,
future direction, priorities, missing systems,
and execution tracking for the Kanasu Trading System.

The roadmap acts as the permanent execution authority
for Kanasu development.

All implementation must follow roadmap order.

No feature, subsystem, refactor, optimization,
or architecture change may be implemented
without first being added to this roadmap.

---

# STATUS DEFINITIONS

| Status | Meaning |
|---|---|
| 🟨 IMPLEMENTING | Currently active implementation |
| 🟥 FUTURE | Planned future implementation |
| 🟩 COMPLETED | Fully implemented and stabilized |
| ⬜ DEFERRED | Intentionally postponed |
| ⬛ CANCELLED | Permanently removed |

---

# ROADMAP EXECUTION RULE

Development flow must always follow:

Roadmap
→ Current Implementing Goal
→ Complete
→ Review
→ Mark Completed
→ Move Next Goal To Implementing
→ Continue

Only ONE roadmap item may remain
in "IMPLEMENTING" state at a time.

---

# MVP v1 — Stable Single-Symbol Research Engine

## Goal

Build a stable, usable, single-symbol trading research system with:
- backtesting
- walk-forward analysis
- replay
- paper trading
- reports
- stable execution workflows

Focus:
- runtime stability
- usability
- workflow correctness
- minimal future refactors

Explicitly excluded from MVP v1:
- multi-symbol systems
- AI/ML systems
- distributed systems
- advanced live trading infrastructure
- portfolio allocation engines

---

| Sl No | Version | Heading | Sub Heading | Minor Goal | Status |
|---|---|---|---|---|---|
| 1 | MVP v1 | Stabilize unified runtime workflows | 🟩 COMPLETED |
| 2 | MVP v1 | Backtesting | Execution Runtime | Stable end-to-end backtest execution | 🟩 COMPLETED |
| 3 | MVP v1 | Portfolio | Portfolio Lifecycle | Stable single-symbol portfolio management |🟨 IMPLEMENTING|
| 4 | MVP v1 | Journaling | Runtime Journals | Stable execution journaling | 🟥 FUTURE |
| 5 | MVP v1 | Reporting | Metrics | Basic performance metrics generation | 🟥 FUTURE |
| 6 | MVP v1 | WFA | Window Engine | WFA execution workflow stabilization | 🟥 FUTURE |
| 7 | MVP v1 | WFA | Optimization Flow | OOS testing pipeline | 🟥 FUTURE |
| 8 | MVP v1 | Replay | Visualization Runtime | Candle replay control system | 🟥 FUTURE |
| 9 | MVP v1 | Replay | Chart Integration | TradingView replay synchronization | 🟥 FUTURE |
| 10 | MVP v1 | Paper Trading | Live Runtime | Separate paper trading runtime | 🟥 FUTURE |
| 11 | MVP v1 | Paper Trading | WebSocket Flow | Stable live candle ingestion | 🟥 FUTURE |
| 12 | MVP v1 | Paper Trading | Execution Engine | Paper order execution flow | 🟥 FUTURE |
| 13 | MVP v1 | Reporting | Session Reports | Trade & equity report generation | 🟥 FUTURE |
| 14 | MVP v1 | Persistence | Session Storage | Minimal session result persistence | 🟥 FUTURE |
| 15 | MVP v1 | Validation | Runtime Testing | Runtime stability test expansion | 🟥 FUTURE |
| 16 | MVP v1 | UI Integration | Backtest UI | Connect execution workflow to frontend | 🟥 FUTURE |
| 17 | MVP v1 | UI Integration | Replay UI | Replay controls integration | 🟥 FUTURE |
| 18 | MVP v1 | Validation | Workflow Validation | Full MVP workflow validation | 🟥 FUTURE |

---

# MVP v2 — Research Professionalization

## Goal

Improve research quality, persistence,
analytics, replay capability,
and reporting professionalization.

Focus:
- structured persistence
- analytics improvements
- export systems
- optimization tooling
- research reproducibility

---

| Sl No | Version | Heading | Sub Heading | Minor Goal | Status |
|---|---|---|---|---|---|
| 19 | MVP v2 | Artifacts | Session Persistence | Structured artifact management | 🟥 FUTURE |
| 20 | MVP v2 | Reporting | Advanced Analytics | Drawdown & advanced statistics | 🟥 FUTURE |
| 21 | MVP v2 | Optimization | Parameter Engine | Parameter sweep framework | 🟥 FUTURE |
| 22 | MVP v2 | Replay | Session Replay | Replay from persisted journals | 🟥 FUTURE |
| 23 | MVP v2 | Reporting | Export System | Excel/PDF exports | 🟥 FUTURE |
| 24 | MVP v2 | Metadata | Session Metadata | Full session metadata persistence | 🟥 FUTURE |

---

# MVP v3 — Multi-Symbol & Portfolio Intelligence

## Goal

Expand Kanasu from single-symbol execution
into portfolio-level research and analysis.

Focus:
- multi-symbol orchestration
- capital allocation
- correlation analysis
- sector analysis
- portfolio-level intelligence

---

| Sl No | Version | Heading | Sub Heading | Minor Goal | Status |
|---|---|---|---|---|---|
| 25 | MVP v3 | Multi-Symbol | Execution Engine | Multi-symbol orchestration | 🟥 FUTURE |
| 26 | MVP v3 | Portfolio | Allocation Engine | Portfolio capital allocation | 🟥 FUTURE |
| 27 | MVP v3 | Sector Analysis | Relative Strength | Sector rotation engine | 🟥 FUTURE |
| 28 | MVP v3 | Correlation | Exposure Control | Correlation-aware risk engine | 🟥 FUTURE |

---

# MVP v4 — Advanced Execution & Live Infrastructure

## Goal

Build advanced execution infrastructure
for live trading and operational stability.

Focus:
- live broker execution
- runtime monitoring
- failover handling
- notification systems

---

| Sl No | Version | Heading | Sub Heading | Minor Goal | Status |
|---|---|---|---|---|---|
| 29 | MVP v4 | Live Trading | Broker Runtime | Real broker order execution | 🟥 FUTURE |
| 30 | MVP v4 | Infrastructure | Runtime Monitoring | Runtime health monitoring | 🟥 FUTURE |
| 31 | MVP v4 | Infrastructure | Recovery Systems | Failover & runtime recovery | 🟥 FUTURE |
| 32 | MVP v4 | Alerts | Notification Engine | Telegram/WhatsApp alerts | 🟥 FUTURE |

---

# MVP v5 — AI/ML & Adaptive Systems

## Goal

Introduce intelligent adaptive systems
for market analysis and strategy enhancement.

Focus:
- market regime analysis
- adaptive scoring
- accumulation/distribution learning
- future AI-assisted research

---

| Sl No | Version | Heading | Sub Heading | Minor Goal | Status |
|---|---|---|---|---|---|
| 33 | MVP v5 | AI/ML | Zone Detection | Accumulation/distribution learning | 🟥 FUTURE |
| 34 | MVP v5 | AI/ML | Strategy Intelligence | Adaptive strategy scoring | 🟥 FUTURE |
| 35 | MVP v5 | AI/ML | Market Regime | Regime classification engine | 🟥 FUTURE |

---

# MVP v6 — Distributed Quant Platform

## Goal

Transform Kanasu into a scalable
distributed quant research platform.

Focus:
- distributed execution
- cloud support
- multi-user systems
- scalable orchestration

---

| Sl No | Version | Heading | Sub Heading | Minor Goal | Status |
|---|---|---|---|---|---|
| 36 | MVP v6 | Infrastructure | Distributed Execution | Multi-runtime orchestration | 🟥 FUTURE |
| 37 | MVP v6 | Cloud | Remote Research | Cloud execution support | 🟥 FUTURE |
| 38 | MVP v6 | Platform | Multi-User | User/project separation | 🟥 FUTURE |

---

# ROADMAP MAINTENANCE RULES

1. Roadmap must always reflect actual project state.

2. Every newly discovered requirement must first be inserted into roadmap before implementation.

3. Critical blockers may be inserted at higher priority only after roadmap review.

4. Non-critical additions must be inserted in logical roadmap position.

5. After completion of each goal:
   - mark current item as 🟩 COMPLETED
   - move next item to 🟨 IMPLEMENTING

6. Roadmap updates must be committed to GitHub.

---

# FINAL PRINCIPLE

Kanasu development must remain:
- disciplined
- modular
- incremental
- stability-focused
- workflow-oriented

Priority:
Stable execution workflows
over feature quantity.