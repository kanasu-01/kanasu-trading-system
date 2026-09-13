# HISTORICAL MATERIAL — NOT CURRENT PROJECT GUIDANCE

## Purpose

This file preserves superseded project terminology and observations during the 2026-09-13 documentation migration. It does not define current architecture, status, scope, priorities or validation. Current guidance begins at the repository [README](../../README.md).

The original documents remain recoverable from Git history before the migration baseline at 4305697.

## Earlier project status

The previous Project Status described the project as:

- **Phase 8 — Execution / Risk Validation**
- focused on validating execution, portfolio, risk and drawdown;
- reporting four drawdown tests and one execution test as passing; and
- recommending P&L/portfolio accounting as the next work.

That snapshot preceded the M1 authoritative portfolio, M2 economic-runtime and M3 data-foundation work. “Phase 8” is historical terminology and is not M8.

## Earlier SMA experiment observation

The previous active status contained:

| Field | Earlier recorded value |
|---|---:|
| Symbol | RELIANCE |
| Timeframe | 15m |
| Strategy | SMACrossOver |
| Trades | 23 |
| Win rate | 26.09% |
| Average win | 3.13% |
| Average loss | -1.79% |
| Expectancy | -0.51% |
| Gross P&L | -2172.17 |
| Net P&L | -2877.69 |
| Transaction cost | 705.52 |
| Maximum drawdown | 21.40% |

These are historical development observations. The record lacks a complete dataset range/fingerprint, code revision, effective configuration, run identifier and artifact reference, so it is insufficient as current reproducible validation or evidence of profitability.

## Earlier registry claims

The former root registry described Kanasu as being in an “Architecture & Foundation Phase (~10–15%).” That percentage had no accepted scope/effort denominator and is no longer used.

It also stated that HistoricalFeed converted/validated nothing, and listed AngelOne historical API wiring, data validation, performance analytics/reports and parameter optimization as unimplemented. Those claims became obsolete as the repository evolved. The current architecture records implementation separately from integration and validation.

## Legacy 10.9 terminology

The previous registry named:

- Phase 10.9B — HistoricalFeed introduced
- Phase 10.9C — Broker-aligned historical data access
- Phase 10.9D — CSVBroker added for offline and replay data

These labels remain historical aliases. They are not M10.9B/M10.9C/M10.9D and are not converted into the permanent M-series hierarchy.

## Legacy roadmap serials

The earlier roadmap used table serial numbers, not permanent M-series IDs:

| Old serial | Old version | Capability as recorded |
|---:|---|---|
| 1 | MVP v1 | Stabilize unified runtime workflows |
| 2 | MVP v1 | Backtesting — stable end-to-end execution |
| 3 | MVP v1 | Portfolio — stable single-symbol lifecycle |
| 4 | MVP v1 | Journaling — runtime journals |
| 5 | MVP v1 | Reporting — basic metrics |
| 6 | MVP v1 | WFA — window workflow |
| 7 | MVP v1 | WFA — optimization/OOS flow |
| 8 | MVP v1 | Replay — candle replay controls |
| 9 | MVP v1 | Replay — chart synchronization |
| 10 | MVP v1 | Paper — separate runtime |
| 11 | MVP v1 | Paper — live candle ingestion |
| 12 | MVP v1 | Paper — execution flow |
| 13 | MVP v1 | Reporting — session reports |
| 14 | MVP v1 | Persistence — session storage |
| 15 | MVP v1 | Validation — runtime testing |
| 16 | MVP v1 | UI — backtest integration |
| 17 | MVP v1 | UI — replay integration |
| 18 | MVP v1 | Validation — full workflow |
| 19 | MVP v2 | Artifacts — session persistence |
| 20 | MVP v2 | Reporting — advanced analytics |
| 21 | MVP v2 | Optimization — parameter engine |
| 22 | MVP v2 | Replay — persisted session replay |
| 23 | MVP v2 | Reporting — Excel/PDF export |
| 24 | MVP v2 | Metadata — full session metadata |
| 25 | MVP v3 | Multi-symbol orchestration |
| 26 | MVP v3 | Portfolio allocation |
| 27 | MVP v3 | Sector relative strength |
| 28 | MVP v3 | Correlation-aware exposure |
| 29 | MVP v4 | Real broker execution |
| 30 | MVP v4 | Runtime monitoring |
| 31 | MVP v4 | Failover/runtime recovery |
| 32 | MVP v4 | Telegram/WhatsApp alerts |
| 33 | MVP v5 | AI accumulation/distribution zones |
| 34 | MVP v5 | Adaptive strategy scoring |
| 35 | MVP v5 | Regime classification |
| 36 | MVP v6 | Distributed execution |
| 37 | MVP v6 | Cloud research |
| 38 | MVP v6 | Multi-user platform |

The serials are preserved only for provenance. They are not renamed M1–M38 and do not reserve modern milestone identifiers.

## Migration crosswalk

| Historical concept | Modern location or treatment |
|---|---|
| “Phase 8” execution/risk work | Historical precursor to the completed M1/M2 foundation; no numerical equivalence. |
| 10.9B/C/D | Historical data-access lineage; no modern M-number equivalence. |
| Old serials 1–18 | Their still-relevant outcomes are progressively represented across V1 M0–M9; this is a thematic mapping, not ID conversion. |
| Old “MVP v2” professionalization | Minimum research reproducibility and metric correctness moved into V1; richer artifacts remain future work. |
| Old “MVP v3” | Retained as a V3+ multi-symbol/portfolio horizon. |
| Old “MVP v4” live trading | Real-money execution is now the V2 boundary because it is the next product class after validated V1 paper operation. |
| Old “MVP v5” AI | Preserved under AI-001–AI-010 and progressive research horizons. |
| Old “MVP v6” distributed/cloud/multi-user | Conditional future product direction, not an inevitable release. |

## Compatibility paths

During M3.2, core.market_data.csv_candle_loader became the canonical CSV parser. The older core.data_loaders import path was retained as a compatibility wrapper so existing legacy callers would continue to import the same public function while parsing behavior remained unified.

Compatibility does not establish that every legacy launcher, CSVBroker or replay path is currently supported; those divergences are recorded in DW-012.
