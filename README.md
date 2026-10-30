# Kanasu Trading System

Kanasu is a modular, Python-first trading research system for NSE equities. The current product target is **V1 — Research and Real-Market-Data Paper Trading**: trustworthy historical data, reproducible research, validated backtesting and walk-forward analysis, real market-data ingestion, simulated execution, authoritative portfolio accounting, and a responsive browser interface.

V1 does **not** place real-money broker orders. Controlled real-money execution is a separate V2 objective with additional reconciliation, recovery, operational-safety, broker, exchange, and regulatory gates.

## Current state

M0–M8 and M9.2–M9.3 are complete at their accepted scopes. The approved M9.4q prospective-governance publication is verified at `97c4f5f14c6797f49e0c9510812774d64af5657c`, but the original milestone-level Review 2 and final Human Approval 3 artifacts are not independently retrievable in the current evidence set. M9.4q final closure is therefore **NOT_VERIFIED** for current governance purposes, and M9.5 remains **NOT_ADMITTED / IMPLEMENTATION BLOCKED**.

See [Project Status](docs/PROJECT_STATUS.md) for the dated baseline and current blockers.

## High-level workflow

```text
Historical source / local store / live source
                    ↓
       canonical Candle data boundary
                    ↓
          strategy and risk logic
                    ↓
          simulated execution
                    ↓
    authoritative PortfolioManager state
                    ↓
       results, journals, API and UI
```

## Documentation

- [Product vision](docs/PRODUCT_VISION.md)
- [Current project status](docs/PROJECT_STATUS.md)
- [Architecture](docs/architecture/ARCHITECTURE.md)
- [Architecture decisions](docs/architecture/DECISIONS.md)
- [Roadmap](docs/roadmap/ROADMAP.md)
- [Deferred work](docs/roadmap/DEFERRED_WORK.md)
- [AI research backlog](docs/roadmap/AI_RESEARCH_BACKLOG.md)
- [Validation plan](docs/validation/VALIDATION_PLAN.md)
- [Paper runtime design](docs/design/PAPER_RUNTIME.md)
- [Governance](docs/governance/GOVERNANCE.md)
- [Legacy project snapshot](docs/archive/LEGACY_PROJECT_SNAPSHOT.md)
- [Frontend guide](frontend/README.md)

Agent-specific navigation is in [AGENTS.md](AGENTS.md).

## Setup

Runtime dependencies are declared in `requirements.txt`. Frontend commands and current integration limitations are documented in the [frontend guide](frontend/README.md). Operational commands should be taken from the relevant runtime documentation and current configuration rather than copied from historical material.
