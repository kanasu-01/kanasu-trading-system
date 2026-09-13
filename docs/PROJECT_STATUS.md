# Kanasu Trading System — Project Status

## Current dashboard

| Field | Current value |
|---|---|
| Project | Kanasu Trading System |
| Migration baseline | 2026-09-13 |
| Branch | `m3-offline-foundation-data` |
| HEAD | `4305697 Add SQLite candle persistence` |
| Latest reported test baseline | 86 passed |
| Version | V1 — Research and Real-Market-Data Paper Trading |
| Phase | P1 — Trusted Historical Data Foundation |
| Milestone | M3 — Offline / Historical Market-Data Foundation |
| Step | M3.6 — Local Historical Persistence and Retrieval |
| Lifecycle | IN_PROGRESS |
| Next coding task | M3.6b — Coverage and Missing-Range Planning |

The 86-test result is previously verified evidence at this baseline. Tests were not rerun during the documentation migration dated above.

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

Completion here refers to the accepted scope of each historical task. It does not imply that every component is integrated into a V1 workflow or release-ready.

## Current work

M3.6b establishes retrieval-coverage semantics and deterministic missing-range planning. Stored candles, retrieval coverage, expected-bar completeness, and source policy remain distinct concepts. See [AD-008](architecture/DECISIONS.md#ad-008--retrieval-coverage-and-expected-bar-completeness) and the [Validation Plan](validation/VALIDATION_PLAN.md#m36b-coverage-and-missing-range-planning).

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
