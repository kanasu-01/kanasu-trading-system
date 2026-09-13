# Kanasu Trading System

Kanasu is a modular, Python-first trading research system for NSE equities. The current product target is **V1 — Research and Real-Market-Data Paper Trading**: trustworthy historical data, reproducible research, validated backtesting and walk-forward analysis, real market-data ingestion, simulated execution, authoritative portfolio accounting, and a responsive browser interface.

V1 does **not** place real-money broker orders. Controlled real-money execution is a separate V2 objective with additional reconciliation, recovery, operational-safety, broker, exchange, and regulatory gates.

## Current state

The repository is in **P1 — Trusted Historical Data Foundation**, at **M3.6 — Local Historical Persistence and Retrieval**. SQLite candle persistence is implemented; the next coding task is **M3.6b — Coverage and Missing-Range Planning**.

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
