# Kanasu Trading System — Project Status

## Current dashboard

| Field | Current value |
|---|---|
| Project | Kanasu Trading System |
| Migration baseline | 2026-09-13 |
| Branch | `m3-offline-foundation-data` |
| Documentation governance baseline | `170f618 Restructure Kanasu documentation governance` |
| Implementation verification baseline | `1e8065a Add historical coverage planner` |
| Latest reported test baseline | `111 passed at 1e8065a` |
| Version | V1 — Research and Real-Market-Data Paper Trading |
| Phase | P1 — Trusted Historical Data Foundation |
| Milestone | M3 — Offline / Historical Market-Data Foundation |
| Step | M3.6 — Local Historical Persistence and Retrieval |
| Lifecycle | IN_PROGRESS |
| Next coding task | M3.6c — Local-First Historical Retrieval Service |

The 111-test result was verified at implementation baseline `1e8065a`.

## Completed foundation

- M0 — Repository / foundation hygiene
- M1 — Authoritative simulated portfolio accounting
- M2 and M2.1–M2.4 — Execution economics/accounting correctness
- M3.1 — Candle finite-value validation
- M3.2 — Canonical CSV candle loader
- M3.3a — Dataset identity propagation
- M3.3b — Dataset timezone identity as metadata
- M3.4 — Candle sequence integrity
- M3.5 — Safe historical chunk composition
- M3.6a — SQLite candle persistence
- M3.6b — Coverage and missing-range planning

Completion here refers to the accepted scope of each historical task. It does not imply that every component is integrated into a V1 workflow or release-ready.

## M3.6b validation evidence

- Focused historical coverage tests: 25 passed
- All market-data tests: 51 passed
- Full suite: 111 passed
- `git diff --check`: passed
- Implementation commit: `1e8065a Add historical coverage planner`

## Current work

M3.6b is complete. M3.6c — Local-First Historical Retrieval Service is the next planned coding task and has not started.

M3.6c must integrate local persistence and the coverage planner without conflating stored candles, retrieval coverage, expected-bar completeness, or source policy. DW-010 timestamp/range-bound compatibility and explicit provider empty/partial/failure semantics must be addressed as part of the M3.6c contract before unsafe integration.

## Important V1 blockers

- local-first historical retrieval and historical-path parity;
- explicit timestamp/bound compatibility for local storage integration;
- backtest validity and reproducible research records;
- WFA termination, configuration propagation, and account-metric validity;
- real-market-data ingestion for paper trading;
- an operational paper-session lifecycle;
- API/frontend integration with actual runtime and research results; and
- completion of all V1 validation and release gates.

Technical findings that are deliberately unresolved are recorded in [Deferred Work](roadmap/DEFERRED_WORK.md). The ordered delivery plan is in the [Roadmap](roadmap/ROADMAP.md).

## Release boundary

V1 does not place real-money broker orders. Live execution is deferred to V2 and requires additional execution, reconciliation, recovery, operational-safety, and external acceptance evidence.
